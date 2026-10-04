'use strict';
// Shared helpers for the pr-review scripts. Zero dependencies; node >= 18.
const { execFileSync } = require('child_process');
const fs = require('fs');

function run(cmd, args, opts = {}) {
  try {
    const out = execFileSync(cmd, args, {
      encoding: 'utf8',
      maxBuffer: 64 * 1024 * 1024,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, ...(opts.env || {}) },
    });
    return { ok: true, out };
  } catch (e) {
    return {
      ok: false,
      out: (e.stdout || '').toString(),
      err: (e.stderr || e.message || '').toString(),
      status: typeof e.status === 'number' ? e.status : 1,
    };
  }
}

function runJson(cmd, args, opts = {}) {
  const r = run(cmd, args, opts);
  if (!r.ok) return r;
  try {
    return { ok: true, json: JSON.parse(r.out) };
  } catch (e) {
    return { ok: false, err: `unparseable JSON from ${cmd} ${args.join(' ')}: ${e.message}`, out: r.out };
  }
}

// glab api --paginate emits one JSON array per page; split and flatten them.
function splitGlabPages(out) {
  const pages = [];
  const chunks = out.split(/\n(?=\[)/);
  for (const c of chunks) {
    const t = c.trim();
    if (!t) continue;
    try { pages.push(JSON.parse(t)); continue; } catch { /* fall through */ }
    // Trailing non-JSON noise after a page must not lose the page itself.
    const end = t.lastIndexOf(']');
    if (end > 0) { try { pages.push(JSON.parse(t.slice(0, end + 1))); } catch { /* noise only */ } }
  }
  return pages.flat();
}

function glabPaginated(host, path) {
  const r = run('glab', ['api', '--hostname', host, '--paginate', path], { env: { GITLAB_HOST: host } });
  if (!r.ok) return r;
  return { ok: true, json: splitGlabPages(r.out) };
}

// Pure host classification; the CLI-probe fallback lives in preflight.
function classifyHost(host) {
  if (!host) return null;
  if (host === 'github.com' || /(^|\.)ghe\./.test(host)) return 'github';
  if (/gitlab/.test(host)) return 'gitlab';
  return null;
}

// Parse a PR/MR reference. owner/repo#N is GitHub syntax; group/project!N is GitLab's —
// the separator is a platform signal.
function parsePrRef(ref) {
  let host = null, repo = null, pr = null, platform = null, m;
  if ((m = String(ref || '').match(/^https?:\/\/([^/]+)\/(.+?)\/(?:-\/)?(?:pull|merge_requests)\/(\d+)/))) {
    host = m[1]; repo = m[2].replace(/\/(?:-\/)?$/, ''); pr = Number(m[3]);
  } else if ((m = String(ref || '').match(/^([\w.-]+(?:\/[\w.-]+)+)([#!])(\d+)$/))) {
    repo = m[1]; pr = Number(m[3]); platform = m[2] === '!' ? 'gitlab' : 'github';
  } else if (/^\d+$/.test(String(ref || ''))) {
    pr = Number(ref);
  }
  return { host, repo, pr, platform };
}

// True only when a diff actually changes the policy FILE — a diff header, not the path in prose.
const policyChanged = (d) => /^(diff --git .*|[+]{3} [ab]?\/?.*)\.claude\/review-policy\.md/m.test(d);

function fail(msg, extra = {}) {
  process.stdout.write(JSON.stringify({ ok: false, error: msg, ...extra }, null, 2) + '\n');
  process.exit(1);
}

function emit(obj) {
  process.stdout.write(JSON.stringify(obj, null, 2) + '\n');
}

function readFileArg(p, label) {
  if (!p) fail(`missing required ${label}`);
  if (!fs.existsSync(p)) fail(`${label} not found: ${p}`);
  return fs.readFileSync(p, 'utf8');
}

// Minimal flag parser: --key value / --key (boolean) / positional.
function parseArgs(argv) {
  const flags = {};
  const pos = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const k = a.slice(2);
      if (i + 1 < argv.length && !argv[i + 1].startsWith('--')) { flags[k] = argv[++i]; }
      else flags[k] = true;
    } else pos.push(a);
  }
  return { flags, pos };
}

// Parse the four `##` policy section names out of review-policy markdown.
const POLICY_SECTIONS = ['What blocks merge', 'Scope', 'How findings read', 'Project rules'];
function policySections(md) {
  return POLICY_SECTIONS.filter((s) => new RegExp(`^##\\s+${s}\\s*$`, 'm').test(md));
}

module.exports = { run, runJson, glabPaginated, splitGlabPages, classifyHost, parsePrRef, policyChanged, fail, emit, readFileArg, parseArgs, policySections };
