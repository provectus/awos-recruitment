'use strict';
// Subprocess tests for preflight.js — the entry script executes on require, so it is
// exercised via child_process with a stubbed PATH. No network; gh/glab are generated stubs.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync, spawnSync } = require('node:child_process');

const SCRIPT = path.join(__dirname, 'preflight.js');

function mkStubBin({ ghOk = true, glabOk = true, login = 'stub-user' } = {}) {
  const bin = fs.mkdtempSync(path.join(os.tmpdir(), 'prrev-bin-'));
  const write = (name, body) => {
    const p = path.join(bin, name);
    fs.writeFileSync(p, `#!/bin/sh\n${body}\n`);
    fs.chmodSync(p, 0o755);
  };
  write('gh', ghOk
    ? `case "$1 $2" in "auth status") exit 0;; "api user") echo '{"login":"${login}"}';; *) exit 0;; esac`
    : 'exit 1');
  write('glab', glabOk ? 'exit 0' : 'exit 1');
  return bin;
}

function runPreflight(args, { bin, cwd }) {
  const r = spawnSync(process.execPath, [SCRIPT, ...args], {
    cwd,
    encoding: 'utf8',
    env: { ...process.env, PATH: `${bin}:${process.env.PATH}` },
  });
  let json = null;
  try { json = JSON.parse(r.stdout); } catch { /* asserted by callers */ }
  return { status: r.status, json, stderr: r.stderr };
}

function mkScratchRepo() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'prrev-repo-'));
  const git = (...a) => execFileSync('git', a, { cwd: dir, stdio: 'pipe' });
  git('init', '-q', '-b', 'main');
  git('-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '--allow-empty', '-q', '-m', 'init');
  return dir;
}

test('public ref with stub gh resolves platform and identity', () => {
  const bin = mkStubBin({ login: 'octo-stub' });
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), 'prrev-cwd-')); // no git remote on purpose
  const r = runPreflight(['owner/repo#5'], { bin, cwd });
  assert.strictEqual(r.status, 0);
  assert.strictEqual(r.json.ok, true);
  assert.strictEqual(r.json.platform, 'github'); // from the #N separator, no CLI ambiguity
  assert.strictEqual(r.json.repo, 'owner/repo');
  assert.strictEqual(r.json.pr, 5);
  assert.strictEqual(r.json.me, 'octo-stub');
  assert.strictEqual(r.json.draftHint, 'native');
});

test('unresolvable platform asks instead of guessing (exit 2)', () => {
  const bin = mkStubBin({ ghOk: false, glabOk: false });
  const cwd = fs.mkdtempSync(path.join(os.tmpdir(), 'prrev-cwd-'));
  const r = runPreflight(['12345'], { bin, cwd }); // bare number, no host, no CLIs
  assert.strictEqual(r.status, 2);
  assert.strictEqual(r.json.ok, false);
  assert.strictEqual(r.json.ask, true);
});

test('--local resolves branch and base in a scratch repo', () => {
  const bin = mkStubBin();
  const repo = mkScratchRepo();
  const r = runPreflight(['--local', 'main'], { bin, cwd: repo });
  assert.strictEqual(r.status, 0);
  assert.strictEqual(r.json.ok, true);
  assert.strictEqual(r.json.mode, 'local');
  assert.strictEqual(r.json.branch, 'main');
  assert.strictEqual(r.json.base, 'main'); // explicit base wins
});
