'use strict';
// In-process tests for lib.js's pure functions. Run: node --test <this dir>
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const { parseArgs, policySections, splitGlabPages, classifyHost, parsePrRef, policyChanged, readFileArg } = require('./lib');

test('parseArgs: pairs, booleans, positionals', () => {
  assert.deepStrictEqual(parseArgs(['--pr', '7', '--out', 'dir']), { flags: { pr: '7', out: 'dir' }, pos: [] });
  assert.deepStrictEqual(parseArgs(['--local']), { flags: { local: true }, pos: [] });
  assert.deepStrictEqual(parseArgs(['--immediate', '--thread', 'x']).flags, { immediate: true, thread: 'x' });
  assert.deepStrictEqual(parseArgs(['a', '--k', 'v', 'b']), { flags: { k: 'v' }, pos: ['a', 'b'] });
  assert.deepStrictEqual(parseArgs([]), { flags: {}, pos: [] });
});

test('policySections: exact ## headings only', () => {
  const all = '## What blocks merge\nx\n## Scope\nx\n## How findings read\nx\n## Project rules\n';
  assert.deepStrictEqual(policySections(all), ['What blocks merge', 'Scope', 'How findings read', 'Project rules']);
  assert.deepStrictEqual(policySections('## Scope\n'), ['Scope']);
  assert.deepStrictEqual(policySections('## Scope   \n'), ['Scope']);      // trailing whitespace ok
  assert.deepStrictEqual(policySections('### Scope\n'), []);               // wrong depth
  assert.deepStrictEqual(policySections('## scope\n'), []);                // wrong case
  assert.deepStrictEqual(policySections('text ## Scope\n'), []);           // not line-anchored
  assert.deepStrictEqual(policySections(''), []);
});

test('splitGlabPages: page arrays concatenate in order', () => {
  assert.deepStrictEqual(splitGlabPages('[1,2]'), [1, 2]);
  assert.deepStrictEqual(splitGlabPages('[1,2]\n[3]'), [1, 2, 3]);
  assert.deepStrictEqual(splitGlabPages('[1]\n'), [1]);
  assert.deepStrictEqual(splitGlabPages(''), []);
  assert.deepStrictEqual(splitGlabPages('[1]\nnoise\n[2]'), [1, 2]);       // non-JSON chunk skipped
});

test('classifyHost: name-only classification', () => {
  assert.strictEqual(classifyHost('github.com'), 'github');
  assert.strictEqual(classifyHost('ghe.corp.example'), 'github');
  assert.strictEqual(classifyHost('x.ghe.corp'), 'github');
  assert.strictEqual(classifyHost('gitlab.com'), 'gitlab');
  assert.strictEqual(classifyHost('gitlab.internal.corp'), 'gitlab');
  assert.strictEqual(classifyHost('mygitlab.io'), 'gitlab');
  assert.strictEqual(classifyHost('bitbucket.org'), null);
  assert.strictEqual(classifyHost(null), null);
});

test('parsePrRef: URLs, hash/bang shorthand, bare number', () => {
  assert.deepStrictEqual(parsePrRef('https://github.com/o/r/pull/12'), { host: 'github.com', repo: 'o/r', pr: 12, platform: null });
  assert.deepStrictEqual(parsePrRef('https://gitlab.example.com/g/sub/proj/-/merge_requests/34'), { host: 'gitlab.example.com', repo: 'g/sub/proj', pr: 34, platform: null });
  assert.deepStrictEqual(parsePrRef('owner/repo#7'), { host: null, repo: 'owner/repo', pr: 7, platform: 'github' });
  assert.deepStrictEqual(parsePrRef('group/sub/proj!9'), { host: null, repo: 'group/sub/proj', pr: 9, platform: 'gitlab' });
  assert.deepStrictEqual(parsePrRef('41'), { host: null, repo: null, pr: 41, platform: null });
  assert.deepStrictEqual(parsePrRef('nonsense'), { host: null, repo: null, pr: null, platform: null });
});

test('policyChanged: diff headers, never prose mentions', () => {
  assert.strictEqual(policyChanged('diff --git a/.claude/review-policy.md b/.claude/review-policy.md\n'), true);
  assert.strictEqual(policyChanged('+++ b/.claude/review-policy.md\n'), true);
  assert.strictEqual(policyChanged('+see .claude/review-policy.md for rules\n'), false);
  assert.strictEqual(policyChanged(''), false);
});

test('readFileArg: reads an existing file', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'prrev-lib-'));
  const f = path.join(dir, 'x.txt');
  fs.writeFileSync(f, 'hello');
  assert.strictEqual(readFileArg(f, '--x'), 'hello');
  fs.rmSync(dir, { recursive: true, force: true });
});
