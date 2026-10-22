import { describe, it, expect } from "vitest";

import { diffLines } from "../text-diff.js";

describe("diffLines", () => {
  it("marks removed and added lines inside a hunk with context", () => {
    const d = diffLines("a\nb\nc\nd\ne\n", "a\nb\nC\nd\ne\n", 1);

    expect(d.lines).toEqual(["@@ -2 +2 @@", " b", "-c", "+C", " d"]);
    expect(d.added).toBe(1);
    expect(d.removed).toBe(1);
  });

  it("returns nothing for equal texts", () => {
    expect(diffLines("same\n", "same\n").lines).toEqual([]);
  });

  it("handles a new section appended at the end", () => {
    const d = diffLines("x\n", "x\n\n## Changelog\n", 0);

    expect(d.lines).toEqual(["@@ -2 +2 @@", "+", "+## Changelog"]);
  });
});
