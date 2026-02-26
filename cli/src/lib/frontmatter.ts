import YAML from "yaml";

/**
 * Extracts and parses YAML frontmatter from the beginning of a markdown file.
 *
 * Frontmatter is the YAML block delimited by `---` at the very start of the
 * file content. Returns the parsed object, or `null` if no valid frontmatter
 * is found.
 */
export function parseFrontmatter(
  content: string,
): Record<string, unknown> | null {
  // Must start with "---" on the first line.
  if (!content.startsWith("---")) {
    return null;
  }

  // Find the closing "---" delimiter (not the opening one).
  const closingIndex = content.indexOf("\n---", 3);
  if (closingIndex === -1) {
    return null;
  }

  const yamlBlock = content.slice(3, closingIndex).trim();

  try {
    const parsed: unknown = YAML.parse(yamlBlock);

    // YAML.parse can return null/undefined for empty blocks, or a
    // non-object for scalars. Only return actual objects.
    if (parsed === null || parsed === undefined || typeof parsed !== "object" || Array.isArray(parsed)) {
      return null;
    }

    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
}
