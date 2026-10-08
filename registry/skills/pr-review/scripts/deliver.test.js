'use strict';
// Subprocess tests for deliver.js's routing and contracts. Stubbed PATH gh records its
// argv so tests can assert what would have been sent; nothing reaches a network.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const SCRIPT = path.join(__dirname, 'deliver.js');

function setup({ reviews = '[]' } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'prrev-del-'));
  const bin = path.join(dir, 'bin');
  fs.mkdirSync(bin);
  const argvLog = path.join(dir, 'gh-argv.log');
  const gh = path.join(bin, 'gh');
  fs.writeFileSync(gh, `#!/bin/sh
echo "$@" >> ${JSON.stringify(argvLog)}
case "$*" in
  *"/reviews/"*"/events"*) echo '{}' ;;
  *"/reviews"*) echo '${reviews}' ;;
  *) echo '{}' ;;
esac
`);
  fs.chmodSync(gh, 0o755);
  const ctx = path.join(dir, 'context.json');
  fs.writeFileSync(ctx, JSON.stringify({ platform: 'github', host: 'github.com', repo: 'o/r', pr: 3, me: 'me-stub' }));
  return { dir, bin, ctx, argvLog };
}

function runDeliver(args, { bin }) {
  const r = spawnSync(process.execPath, [SCRIPT, ...args], {
    encoding: 'utf8',
    env: { ...process.env, PATH: `${bin}:${process.env.PATH}` },
  });
  let json = null;
  try { json = JSON.parse(r.stdout); } catch { /* asserted by callers */ }
  return { status: r.status, json, stderr: r.stderr };
}

test('no op: usage error', () => {
  const { bin } = setup();
  const r = runDeliver([], { bin });
  assert.strictEqual(r.status, 1);
  assert.strictEqual(r.json.ok, false);
  assert.match(r.json.error, /usage/);
});

test('unknown op fails loudly', () => {
  const { bin, ctx } = setup();
  const r = runDeliver(['frobnicate', '--context', ctx], { bin });
  assert.strictEqual(r.json.ok, false);
  assert.match(r.json.error, /unknown op: frobnicate/);
});

test('publish-now refuses on GitHub', () => {
  const { bin, ctx, dir } = setup();
  const f = path.join(dir, 'b.md'); fs.writeFileSync(f, 'x');
  const r = runDeliver(['publish-now', '--context', ctx, '--body-file', f, '--comments-file', f], { bin });
  assert.strictEqual(r.json.ok, false);
  assert.match(r.json.error, /GitLab DRAFTS=no path/);
});

test('reply without --thread fails', () => {
  const { bin, ctx, dir } = setup();
  const f = path.join(dir, 'r.md'); fs.writeFileSync(f, 'reply');
  const r = runDeliver(['reply', '--context', ctx, '--body-file', f], { bin });
  assert.strictEqual(r.json.ok, false);
  assert.match(r.json.error, /missing --thread/);
});

test('find-pending with no reviews: null pending, never-destroy off', () => {
  const { bin, ctx } = setup({ reviews: '[]' });
  const r = runDeliver(['find-pending', '--context', ctx], { bin });
  assert.strictEqual(r.json.ok, true);
  assert.strictEqual(r.json.pending, null);
  assert.strictEqual(r.json.neverDestroy, false);
});

test('find-pending detects my pending review and empty body', () => {
  const reviews = JSON.stringify([{ id: 9, node_id: 'N9', state: 'PENDING', body: '', user: { login: 'me-stub' } }]);
  const { bin, ctx } = setup({ reviews });
  const r = runDeliver(['find-pending', '--context', ctx], { bin });
  assert.strictEqual(r.json.neverDestroy, true);
  assert.deepStrictEqual(r.json.pending, { id: 9, nodeId: 'N9', bodyEmpty: true });
});

test('submit validates the event and maps approve to APPROVE', () => {
  const reviews = JSON.stringify([{ id: 9, node_id: 'N9', state: 'PENDING', body: 'b', user: { login: 'me-stub' } }]);
  const { bin, ctx, argvLog } = setup({ reviews });
  const bad = runDeliver(['submit', '--context', ctx, '--event', 'nonsense'], { bin });
  assert.strictEqual(bad.json.ok, false);
  assert.match(bad.json.error, /--event must be/);
  const good = runDeliver(['submit', '--context', ctx, '--event', 'approve'], { bin });
  assert.strictEqual(good.json.ok, true);
  const logged = fs.readFileSync(argvLog, 'utf8');
  assert.match(logged, /reviews\/9\/events/);
  assert.match(logged, /event=APPROVE/);
});
