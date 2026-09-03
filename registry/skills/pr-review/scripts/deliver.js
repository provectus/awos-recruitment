#!/usr/bin/env node
'use strict';
// deliver.js — delivery operations for pr-review (public mode), both platforms.
// Only runs AFTER the user approved at the results gate; the script posts, the skill decides.
//
//   node deliver.js <op> --context <context.json> [op flags]
//
// Ops:
//   find-pending
//   create-draft  --body-file F --comments-file J     J: [{path,line,startLine?,body}]
//   publish-now   --body-file F --comments-file J     (GitLab DRAFTS=no path: live discussions, stop at first failure)
//   reply         --thread ID --body-file F [--immediate]
//   reply-top     --body-file F
//   update-draft-note --id ID --body-file F           (GitLab)
//   submit        --event approve|request_changes|comment [--body-file F]
//
// Every op prints one JSON result. Any {ok:false} means stop and tell the user — never improvise past it.
const fs = require('fs');
const { run, runJson, fail, emit, readFileArg, parseArgs } = require('./lib');

const { flags, pos } = parseArgs(process.argv.slice(2));
const op = pos[0];
if (!op) fail('usage: deliver.js <op> --context <context.json> ...');
const ctx = JSON.parse(readFileArg(flags.context, '--context'));
const { platform, host, repo, pr } = ctx;
const env = { GITLAB_HOST: host };
const project = encodeURIComponent(repo);
const glabBase = `projects/${project}/merge_requests/${pr}`;

function ghFindPending() {
  const r = run('gh', ['api', `repos/${repo}/pulls/${pr}/reviews`]);
  if (!r.ok) fail(`reviews fetch failed: ${r.err}`);
  let list = [];
  try { const j = JSON.parse(r.out); if (Array.isArray(j)) list = j; } catch { /* empty or non-JSON = no reviews */ }
  const p = list.find((x) => x.user && x.user.login === ctx.me && x.state === 'PENDING');
  return p ? { id: p.id, nodeId: p.node_id, bodyEmpty: !(p.body && p.body.trim()) } : null;
}
function glDrafts() {
  const r = runJson('glab', ['api', '--hostname', host, `${glabBase}/draft_notes`], { env });
  if (!r.ok) fail(`draft_notes fetch failed: ${r.err}`);
  return r.json;
}

if (op === 'find-pending') {
  if (platform === 'github') {
    const p = ghFindPending();
    emit({ ok: true, pending: p, neverDestroy: !!p });
  } else {
    const notes = glDrafts();
    emit({ ok: true, pending: notes.length ? { baseline: notes.length, notes: notes.map((n) => ({ id: n.id, path: n.position ? n.position.new_path : null, snippet: (n.note || '').slice(0, 80) })) } : null,
      neverDestroy: notes.length > 0,
      note: 'GitLab drafts append — never DELETE; bulk_publish publishes the user\'s drafts too, so tell them before appending.' });
  }
  process.exit(0);
}

if (op === 'create-draft') {
  const body = readFileArg(flags['body-file'], '--body-file');
  const comments = JSON.parse(readFileArg(flags['comments-file'], '--comments-file'));
  if (platform === 'github') {
    if (ghFindPending()) fail('a pending review already exists — never-destroy rule: stop and ask the user', { neverDestroy: true });
    const payload = { body, comments: comments.map((c) => ({ path: c.path, line: c.line, side: 'RIGHT', body: c.body, ...(c.startLine ? { start_line: c.startLine } : {}) })) };
    const tmp = `${flags['body-file']}.payload.json`;
    fs.writeFileSync(tmp, JSON.stringify(payload));
    let r = run('gh', ['api', '-X', 'POST', `repos/${repo}/pulls/${pr}/reviews`, '--input', tmp]);
    const rejected = [];
    if (!r.ok && /line must be part of the diff/i.test(r.err + r.out)) {
      // Retry without out-of-diff comments; the skill folds them into the summary.
      emit({ ok: false, retryable: true, error: 'a comment targets a line outside the diff — move it into the summary body and re-run', raw: (r.err + r.out).slice(0, 400) });
      process.exit(1);
    }
    if (!r.ok) fail(`create draft failed: ${(r.err + r.out).slice(0, 400)}`);
    const p = ghFindPending();
    if (!p) fail('POST succeeded but no pending review found — verify manually');
    emit({ ok: true, pending: p, bodyEmpty: p.bodyEmpty, rejected,
      warning: p.bodyEmpty ? 'summary body landed EMPTY (known MCP/API failure) — it cannot be edited in place; deliver the summary at submit time and print it verbatim in step 7' : null });
  } else {
    // GitLab: one draft note per finding, id-tracked, anchoring verified; positionless summary note last.
    const refs = ctx.diffRefs;
    if (!refs) fail('no diff_refs in context — refetch context (stale SHAs get positions rejected)');
    const postedIds = [];
    for (const c of comments) {
      const args = ['api', '--hostname', host, '-X', 'POST', `${glabBase}/draft_notes`,
        '--form', `note=${c.body}`,
        '--form', 'position[position_type]=text',
        '--form', `position[base_sha]=${refs.base_sha}`,
        '--form', `position[start_sha]=${refs.start_sha}`,
        '--form', `position[head_sha]=${refs.head_sha}`,
        '--form', `position[old_path]=${c.oldPath || c.path}`,
        '--form', `position[new_path]=${c.path}`];
      if (c.oldLine) args.push('--form', `position[old_line]=${c.oldLine}`);
      if (c.line) args.push('--form', `position[new_line]=${c.line}`);
      const r = runJson('glab', args, { env });
      if (!r.ok || !r.json.id) {
        emit({ ok: false, error: `draft note POST failed at ${c.path}:${c.line} — stop; posted so far: ${postedIds.length}/${comments.length}`,
          postedIds, raw: (r.err || r.out || '').slice(0, 400) });
        process.exit(1);
      }
      postedIds.push(r.json.id);
    }
    const sum = runJson('glab', ['api', '--hostname', host, '-X', 'POST', `${glabBase}/draft_notes`, '--form', `note=${body}`], { env });
    if (!sum.ok) fail(`summary draft note failed — inline notes are up (${postedIds.length}); summary must ride bulk_publish note= instead`, { postedIds });
    // Anchoring check: every posted inline id must exist WITH a path and a line.
    const all = glDrafts();
    const report = postedIds.map((id) => {
      const n = all.find((x) => x.id === id);
      if (!n) return { id, status: 'MISSING' };
      const pos2 = n.position || {};
      if (!pos2.new_path || (pos2.new_line == null && pos2.old_line == null)) return { id, status: 'UNANCHORED' };
      return { id, status: 'ok', at: `${pos2.new_path}:${pos2.new_line ?? pos2.old_line}` };
    });
    const bad = report.filter((r) => r.status !== 'ok');
    emit({ ok: bad.length === 0, postedIds, summaryNoteId: sum.json.id, anchoring: report,
      error: bad.length ? 'anchoring check failed — delivery has NOT succeeded; fix before telling the user anything landed' : undefined,
      note: 'summary exists as a positionless draft — do NOT also pass note= to bulk_publish (it would double-post)' });
  }
  process.exit(0);
}

if (op === 'publish-now') {
  if (platform !== 'gitlab') fail('publish-now is the GitLab DRAFTS=no path; on GitHub use submit');
  readFileArg(flags['body-file'], '--body-file'); // validate up front; the summary itself posts later via reply-top
  const comments = JSON.parse(readFileArg(flags['comments-file'], '--comments-file'));
  const refs = ctx.diffRefs || {};
  const posted = []; const remaining = [...comments];
  for (const c of comments) {
    const args = ['api', '--hostname', host, '-X', 'POST', `${glabBase}/discussions`,
      '--form', `body=${c.body}`,
      '--form', 'position[position_type]=text',
      '--form', `position[base_sha]=${refs.base_sha}`,
      '--form', `position[start_sha]=${refs.start_sha}`,
      '--form', `position[head_sha]=${refs.head_sha}`,
      '--form', `position[old_path]=${c.oldPath || c.path}`,
      '--form', `position[new_path]=${c.path}`,
      '--form', `position[new_line]=${c.line}`];
    const r = runJson('glab', args, { env });
    if (!r.ok) break; // stop at first failure — a partial review is a state to escape, not extend
    posted.push(remaining.shift());
  }
  // Summary posts on BOTH paths; on abort the skill folds `remaining` verbatim into it first.
  emit({ ok: remaining.length === 0, posted: posted.length, remaining,
    summaryPosted: false,
    next: remaining.length
      ? 'ABORTED mid-list: fold every remaining finding verbatim into the summary, then post it with reply-top'
      : 'post the summary with reply-top' });
  process.exit(0);
}

if (op === 'reply') {
  const body = readFileArg(flags['body-file'], '--body-file');
  const thread = flags.thread;
  if (!thread) fail('missing --thread');
  if (platform === 'github') {
    const p = ghFindPending();
    if (p && !flags.immediate) {
      const r = runJson('gh', ['api', 'graphql', '-f', `query=mutation { addPullRequestReviewThreadReply(input:{ pullRequestReviewId:"${p.nodeId}", pullRequestReviewThreadId:"${thread}", body:${JSON.stringify(body)} }) { comment { url } } }`]);
      if (!r.ok) fail(`pending-review thread reply failed: ${r.err}`);
      emit({ ok: true, via: 'pending-review (publishes atomically on submit)' });
    } else {
      const r = runJson('gh', ['api', '-X', 'POST', `repos/${repo}/pulls/${pr}/comments/${thread}/replies`, '-f', `body=${body}`]);
      if (!r.ok) fail(`reply failed (note: 422 while a pending review exists — use the pending path): ${r.err}`);
      emit({ ok: true, id: r.json.id });
    }
  } else {
    if (flags.immediate) {
      const r = runJson('glab', ['api', '--hostname', host, '-X', 'POST', `${glabBase}/discussions/${thread}/notes`, '-f', `body=${body}`], { env });
      if (!r.ok) fail(`reply failed: ${r.err}`);
      emit({ ok: true, id: r.json.id });
    } else {
      const r = runJson('glab', ['api', '--hostname', host, '-X', 'POST', `${glabBase}/draft_notes`, '--form', `note=${body}`, '--form', `in_reply_to_discussion_id=${thread}`], { env });
      if (!r.ok) fail(`draft reply failed: ${r.err}`);
      emit({ ok: true, id: r.json.id, via: 'draft (publishes with the review)' });
    }
  }
  process.exit(0);
}

if (op === 'reply-top') {
  const body = readFileArg(flags['body-file'], '--body-file');
  if (platform === 'github') {
    const r = run('gh', ['pr', 'comment', String(pr), '--repo', repo, '--body-file', flags['body-file']]);
    if (!r.ok) fail(`comment failed: ${r.err}`);
    emit({ ok: true });
  } else {
    const r = run('glab', ['mr', 'note', 'create', String(pr), '-R', `https://${host}/${repo}`, '-m', body], { env });
    if (!r.ok) fail(`note failed: ${r.err}`);
    emit({ ok: true });
  }
  process.exit(0);
}

if (op === 'update-draft-note') {
  if (platform !== 'gitlab') fail('update-draft-note is GitLab-only; GitHub pending comments are edited via the UI or resubmission');
  const body = readFileArg(flags['body-file'], '--body-file');
  const r = runJson('glab', ['api', '--hostname', host, '-X', 'PUT', `${glabBase}/draft_notes/${flags.id}`, '--form', `note=${body}`], { env });
  if (!r.ok) fail(`update failed: ${r.err}`);
  emit({ ok: true, id: flags.id, note: 'position preserved — text replaced' });
  process.exit(0);
}

if (op === 'submit') {
  const event = String(flags.event || '').toLowerCase();
  if (platform === 'github') {
    const p = ghFindPending();
    if (!p) fail('no pending review to submit');
    const map = { approve: 'APPROVE', request_changes: 'REQUEST_CHANGES', comment: 'COMMENT' };
    if (!map[event]) fail('--event must be approve|request_changes|comment');
    const args = ['api', '-X', 'POST', `repos/${repo}/pulls/${pr}/reviews/${p.id}/events`, '-f', `event=${map[event]}`];
    if (flags['body-file']) args.push('-f', `body=${readFileArg(flags['body-file'], '--body-file')}`);
    const r = run('gh', args);
    if (!r.ok) {
      if (/approve your own/i.test(r.err + r.out)) fail('cannot approve your own PR — switch the verdict to comment');
      fail(`submit failed: ${(r.err + r.out).slice(0, 300)}`);
    }
    emit({ ok: true, submitted: map[event] });
  } else {
    const args = ['api', '--hostname', host, '-X', 'POST', `${glabBase}/draft_notes/bulk_publish`];
    if (event === 'request_changes' || event === 'comment') args.push('--form', `reviewer_state=${event === 'comment' ? 'reviewed' : 'requested_changes'}`);
    if (flags['body-file']) args.push('--form', `note=${readFileArg(flags['body-file'], '--body-file')}`); // only when no positionless summary draft exists
    let r = run('glab', args, { env });
    if (!r.ok && /reviewer_state/.test(r.err + r.out)) {
      r = run('glab', ['api', '--hostname', host, '-X', 'POST', `${glabBase}/draft_notes/bulk_publish`], { env });
    }
    if (!r.ok) fail(`bulk_publish failed: ${(r.err + r.out).slice(0, 300)}`);
    if (event === 'approve') {
      const a = run('glab', ['mr', 'approve', String(pr), '-R', `https://${host}/${repo}`], { env });
      if (!a.ok) fail(`published, but approve failed (author cannot approve own MR?): ${(a.err + a.out).slice(0, 200)}`);
    }
    emit({ ok: true, submitted: event });
  }
  process.exit(0);
}

fail(`unknown op: ${op}`);
