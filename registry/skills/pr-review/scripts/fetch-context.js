#!/usr/bin/env node
'use strict';
// fetch-context.js — fetch and normalize everything pr-review's step 1 needs, in one pass,
// with the same JSON shape for GitHub and GitLab. Read-only.
//
//   node fetch-context.js --platform github|gitlab --host H --repo OWNER/REPO --pr N --me LOGIN --out DIR
//
// Writes:  DIR/context.json  (full normalized context)
//          DIR/diff.patch    (the unified diff — hand agents this path, not inline text)
// Stdout:  a compact summary + the two paths. Read context.json selectively; don't re-fetch.
const fs = require('fs');
const path = require('path');
const { run, runJson, glabPaginated, policyChanged, fail, emit, parseArgs, policySections } = require('./lib');

const { flags } = parseArgs(process.argv.slice(2));
const { platform, host, repo, me } = flags;
const pr = Number(flags.pr);
// Default out dir is INSIDE the repo under review and unique per PR — a shared /tmp path
// gets clobbered when two reviews run concurrently on the same machine.
const outDir = flags.out || `review/.pr-${pr}-context`;
if (!platform || !repo || !pr) fail('usage: fetch-context.js --platform github|gitlab --host H --repo O/R --pr N --me LOGIN [--out DIR]');
fs.mkdirSync(outDir, { recursive: true });

const ctx = { platform, host, repo, pr, me: me || null, fetchedAt: null,
  meta: null, draftCapable: null, draftCapabilityNote: null, diffRefs: null,
  threads: [], topLevel: [], myPriorInline: [], myLastActivityAt: null,
  pending: null, policy: { exists: false, sections: [], prModifiesPolicy: false },
  warnings: [] };

let diffText = '';

if (platform === 'github') {
  const metaR = runJson('gh', ['pr', 'view', String(pr), '--repo', repo, '--json',
    'number,title,author,body,headRefName,baseRefName,additions,deletions,changedFiles,url']);
  if (!metaR.ok) fail(`gh pr view failed: ${metaR.err || metaR.out}`);
  ctx.meta = metaR.json;
  ctx.draftCapable = true; // native pending reviews

  const diffR = run('gh', ['pr', 'diff', String(pr), '--repo', repo]);
  if (!diffR.ok) ctx.warnings.push(`diff fetch failed: ${diffR.err}`); else diffText = diffR.out;

  const [owner, name] = repo.split('/');
  const gql = runJson('gh', ['api', 'graphql', '-F', `owner=${owner}`, '-F', `repo=${name}`, '-F', `n=${pr}`, '-f', `query=
    query($owner:String!,$repo:String!,$n:Int!){ repository(owner:$owner,name:$repo){ pullRequest(number:$n){
      url reviews(first:50){ nodes{ author{login} state submittedAt body } }
      reviewThreads(first:100){ nodes{ id isResolved path line
        comments(first:50){ nodes{ databaseId author{login} body createdAt url originalLine } } } }
      comments(first:100){ nodes{ databaseId author{login} body createdAt url } } } } }`]);
  if (!gql.ok) fail(`comments fetch failed: ${gql.err || gql.out}`);
  const prNode = gql.json.data.repository.pullRequest;
  ctx.threads = (prNode.reviewThreads.nodes || []).map((t) => {
    const cs = t.comments.nodes || [];
    const first = cs[0] || {};
    return { id: t.id, replyTargetId: first.databaseId ?? null, resolved: !!t.isResolved,
      outdated: !!t.isOutdated, path: t.path ?? null, line: t.line ?? first.originalLine ?? null,
      lastAuthor: cs.length ? cs[cs.length - 1].author.login : null,
      mineLast: cs.length ? cs[cs.length - 1].author.login === me : false,
      comments: cs.map((c) => ({ id: c.databaseId, author: c.author.login, body: c.body, createdAt: c.createdAt })) };
  });
  ctx.topLevel = (prNode.comments.nodes || []).map((c) => ({ id: c.databaseId, author: c.author.login, body: c.body, createdAt: c.createdAt }));
  ctx.myPriorInline = ctx.threads.filter((t) => t.comments.some((c) => c.author === me))
    .map((t) => ({ threadId: t.id, path: t.path, line: t.line, resolved: t.resolved }));
  const myTimes = [
    ...(prNode.reviews.nodes || []).filter((r) => r.author && r.author.login === me).map((r) => r.submittedAt),
    ...ctx.threads.flatMap((t) => t.comments.filter((c) => c.author === me).map((c) => c.createdAt)),
  ].filter(Boolean).sort();
  ctx.myLastActivityAt = myTimes.length ? myTimes[myTimes.length - 1] : null;

  const revs = runJson('gh', ['api', `repos/${repo}/pulls/${pr}/reviews`]);
  if (revs.ok && Array.isArray(revs.json)) {
    const p = revs.json.find((r) => r.user && r.user.login === me && r.state === 'PENDING');
    ctx.pending = p ? { id: p.id, nodeId: p.node_id, bodyEmpty: !(p.body && p.body.trim()) } : null;
  }

  const polR = run('gh', ['api', `repos/${repo}/contents/.claude/review-policy.md?ref=${ctx.meta.baseRefName}`, '-q', '.content']);
  if (polR.ok && polR.out.trim()) {
    const md = Buffer.from(polR.out.trim(), 'base64').toString('utf8');
    ctx.policy = { exists: true, sections: policySections(md), prModifiesPolicy: policyChanged(diffText), markdown: md };
  } else {
    ctx.policy.prModifiesPolicy = policyChanged(diffText);
    if (ctx.policy.prModifiesPolicy) ctx.warnings.push('base policy not fetchable via API but this PR modifies .claude/review-policy.md — reconstruct the BASE version from the diff context lines; the PR head version must not govern its own review');
  }
} else if (platform === 'gitlab') {
  const env = { GITLAB_HOST: host };
  const project = encodeURIComponent(repo);
  const metaR = runJson('glab', ['api', '--hostname', host, `projects/${project}/merge_requests/${pr}`], { env });
  if (!metaR.ok) fail(`MR fetch failed: ${metaR.err || metaR.out}`);
  const mr = metaR.json;
  ctx.meta = { number: mr.iid, title: mr.title, author: mr.author && mr.author.username, body: mr.description,
    headRefName: mr.source_branch, baseRefName: mr.target_branch, url: mr.web_url };
  ctx.diffRefs = mr.diff_refs || null;
  if (!ctx.diffRefs) {
    const v = runJson('glab', ['api', '--hostname', host, `projects/${project}/merge_requests/${pr}/versions`], { env });
    if (v.ok && v.json[0]) ctx.diffRefs = { base_sha: v.json[0].base_commit_sha, start_sha: v.json[0].start_commit_sha, head_sha: v.json[0].head_commit_sha };
  }

  const diffR = run('glab', ['mr', 'diff', String(pr), '-R', `https://${host}/${repo}`], { env });
  if (!diffR.ok) ctx.warnings.push(`diff fetch failed: ${diffR.err}`); else diffText = diffR.out;

  // Draft capability: GET proves read; token scope decides write. Provisional until the first POST succeeds.
  const probe = run('glab', ['api', '--hostname', host, `projects/${project}/merge_requests/${pr}/draft_notes`], { env });
  let scopes = null;
  const tok = runJson('glab', ['api', '--hostname', host, 'personal_access_tokens/self'], { env });
  if (tok.ok && Array.isArray(tok.json.scopes)) scopes = tok.json.scopes;
  ctx.draftCapable = probe.ok && (!scopes || scopes.includes('api'));
  ctx.draftCapabilityNote = !probe.ok ? 'draft_notes endpoint unreadable (absent, or token cannot see it)'
    : scopes && !scopes.includes('api') ? `token scopes ${scopes.join(',')} — read_api cannot write drafts`
    : 'provisional until the first draft POST succeeds';

  const disc = glabPaginated(host, `projects/${project}/merge_requests/${pr}/discussions`);
  if (!disc.ok) fail(`discussions fetch failed: ${disc.err}`);
  for (const d of disc.json) {
    const notes = (d.notes || []).filter((n) => !n.system);
    if (!notes.length) continue;
    const first = notes[0];
    const posOf = (n) => (n.position ? { path: n.position.new_path || n.position.old_path, line: n.position.new_line ?? n.position.old_line } : { path: null, line: null });
    const p = posOf(first);
    const item = { id: d.id, replyTargetId: d.id, resolved: notes.every((n) => !n.resolvable || n.resolved),
      outdated: false, path: p.path, line: p.line,
      lastAuthor: notes[notes.length - 1].author.username,
      mineLast: notes[notes.length - 1].author.username === me,
      comments: notes.map((n) => ({ id: n.id, author: n.author.username, body: n.body, createdAt: n.created_at })) };
    if (d.individual_note) ctx.topLevel.push({ id: first.id, author: first.author.username, body: first.body, createdAt: first.created_at });
    else ctx.threads.push(item);
  }
  ctx.myPriorInline = ctx.threads.filter((t) => t.comments.some((c) => c.author === me))
    .map((t) => ({ threadId: t.id, path: t.path, line: t.line, resolved: t.resolved }));
  const myTimes = ctx.threads.concat([{ comments: ctx.topLevel }])
    .flatMap((t) => t.comments.filter((c) => c.author === me).map((c) => c.createdAt)).filter(Boolean).sort();
  ctx.myLastActivityAt = myTimes.length ? myTimes[myTimes.length - 1] : null;

  const drafts = runJson('glab', ['api', '--hostname', host, `projects/${project}/merge_requests/${pr}/draft_notes`], { env });
  ctx.pending = drafts.ok && Array.isArray(drafts.json) && drafts.json.length
    ? { baseline: drafts.json.length, notes: drafts.json.map((n) => ({ id: n.id, path: n.position ? n.position.new_path : null })) }
    : null;

  const polR = runJson('glab', ['api', '--hostname', host,
    `projects/${project}/repository/files/${encodeURIComponent('.claude/review-policy.md')}?ref=${encodeURIComponent(ctx.meta.baseRefName)}`], { env });
  if (polR.ok && polR.json.content) {
    const md = Buffer.from(polR.json.content, 'base64').toString('utf8');
    ctx.policy = { exists: true, sections: policySections(md), prModifiesPolicy: policyChanged(diffText), markdown: md };
  } else {
    ctx.policy.prModifiesPolicy = policyChanged(diffText);
  }
} else {
  fail(`unknown platform: ${platform}`);
}

if (ctx.policy.prModifiesPolicy) ctx.warnings.push('this PR MODIFIES .claude/review-policy.md — tell the user at the gate; the base-branch version governs this review, the change takes effect next review');
ctx.fetchedAt = new Date().toISOString();
// Absolute paths in all output — the session and its subagents may run with different cwds.
const diffPath = path.resolve(outDir, 'diff.patch');
const ctxPath = path.resolve(outDir, 'context.json');
fs.writeFileSync(diffPath, diffText);
fs.writeFileSync(ctxPath, JSON.stringify(ctx, null, 2));

const open = ctx.threads.filter((t) => !t.resolved).length;
emit({ ok: true, contextFile: ctxPath, diffFile: diffPath,
  summary: {
    url: ctx.meta && ctx.meta.url, base: ctx.meta && ctx.meta.baseRefName, head: ctx.meta && ctx.meta.headRefName,
    threads: ctx.threads.length, openThreads: open, topLevel: ctx.topLevel.length,
    myPriorInline: ctx.myPriorInline.length, myLastActivityAt: ctx.myLastActivityAt,
    pending: !!ctx.pending, draftCapable: ctx.draftCapable, draftCapabilityNote: ctx.draftCapabilityNote,
    policy: ctx.policy.exists ? ctx.policy.sections : 'none', prModifiesPolicy: ctx.policy.prModifiesPolicy,
    warnings: ctx.warnings,
  } });
