/**
 * A small line diff with unified-style output, enough to show what an update
 * changes in a skill. No dependency: skill files are a few hundred lines, so
 * a plain longest-common-subsequence table is fast enough.
 */

/** Above this many cells the table would be slow; report the change without lines. */
const MAX_CELLS = 4_000_000;

export interface DiffResult {
  /** Lines with a "-", "+" or " " prefix and "@@" hunk headers. */
  lines: string[];
  added: number;
  removed: number;
  /** True when the files were too large to compare line by line. */
  tooLarge: boolean;
}

export function diffLines(oldText: string, newText: string, context = 2): DiffResult {
  const a = splitLines(oldText);
  const b = splitLines(newText);

  if (a.length * b.length > MAX_CELLS) {
    return { lines: [], added: b.length, removed: a.length, tooLarge: true };
  }

  // lcs[i][j] = length of the LCS of a[i..] and b[j..].
  const lcs: Uint32Array[] = Array.from({ length: a.length + 1 }, () => new Uint32Array(b.length + 1));
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
    }
  }

  // Walk the table into a list of operations.
  type Op = { kind: " " | "-" | "+"; text: string; aLine: number; bLine: number };
  const ops: Op[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) {
      ops.push({ kind: " ", text: a[i], aLine: i, bLine: j });
      i++;
      j++;
    } else if (i < a.length && (j === b.length || lcs[i + 1][j] >= lcs[i][j + 1])) {
      // Removals before additions, as in `diff -u`.
      ops.push({ kind: "-", text: a[i], aLine: i, bLine: j });
      i++;
    } else {
      ops.push({ kind: "+", text: b[j], aLine: i, bLine: j });
      j++;
    }
  }

  // Keep changes plus `context` unchanged lines around them, grouped into hunks.
  const keep = new Array<boolean>(ops.length).fill(false);
  ops.forEach((op, k) => {
    if (op.kind !== " ") {
      for (let c = Math.max(0, k - context); c <= Math.min(ops.length - 1, k + context); c++) {
        keep[c] = true;
      }
    }
  });

  const lines: string[] = [];
  let added = 0;
  let removed = 0;
  let k = 0;
  while (k < ops.length) {
    if (!keep[k]) {
      k++;
      continue;
    }
    const start = k;
    while (k < ops.length && keep[k]) {
      k++;
    }
    const hunk = ops.slice(start, k);
    lines.push(`@@ -${hunk[0].aLine + 1} +${hunk[0].bLine + 1} @@`);
    for (const op of hunk) {
      lines.push(`${op.kind}${op.text}`);
      if (op.kind === "+") added++;
      if (op.kind === "-") removed++;
    }
  }

  return { lines, added, removed, tooLarge: false };
}

function splitLines(text: string): string[] {
  if (text === "") {
    return [];
  }
  const lines = text.split("\n");
  if (lines.at(-1) === "") {
    lines.pop();
  }
  return lines;
}
