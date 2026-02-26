import { describe, it, expect } from "vitest";

import { parseFrontmatter } from "../frontmatter.js";

describe("parseFrontmatter", () => {
  // -----------------------------------------------------------------------
  // 1. Valid frontmatter
  // -----------------------------------------------------------------------
  it("returns parsed object with all fields from valid frontmatter", () => {
    const content = `---
name: my-agent
description: A helpful agent
model: claude-sonnet
skills:
  - typescript
  - testing
---

# My Agent

Body content here.
`;

    const result = parseFrontmatter(content);

    expect(result).toEqual({
      name: "my-agent",
      description: "A helpful agent",
      model: "claude-sonnet",
      skills: ["typescript", "testing"],
    });
  });

  // -----------------------------------------------------------------------
  // 2. No frontmatter delimiters
  // -----------------------------------------------------------------------
  it("returns null when there are no frontmatter delimiters", () => {
    const content = `# Just a markdown file

No frontmatter here.
`;

    expect(parseFrontmatter(content)).toBeNull();
  });

  // -----------------------------------------------------------------------
  // 3. Malformed YAML
  // -----------------------------------------------------------------------
  it("returns null for malformed YAML", () => {
    const content = `---
name: [invalid yaml
  - not: {properly: closed
---

Body.
`;

    expect(parseFrontmatter(content)).toBeNull();
  });

  // -----------------------------------------------------------------------
  // 4. Empty skills list
  // -----------------------------------------------------------------------
  it("returns empty array for empty skills list", () => {
    const content = `---
name: minimal-agent
description: Minimal
skills: []
---

Body.
`;

    const result = parseFrontmatter(content);

    expect(result).not.toBeNull();
    expect(result!.skills).toEqual([]);
  });

  // -----------------------------------------------------------------------
  // 5. Content without closing delimiter
  // -----------------------------------------------------------------------
  it("returns null when the closing --- delimiter is missing", () => {
    const content = `---
name: incomplete
description: No closing delimiter

Body content without closing delimiter.
`;

    expect(parseFrontmatter(content)).toBeNull();
  });

  // -----------------------------------------------------------------------
  // 6. Empty YAML block
  // -----------------------------------------------------------------------
  it("returns null for an empty YAML block", () => {
    const content = `---
---

Body.
`;

    expect(parseFrontmatter(content)).toBeNull();
  });
});
