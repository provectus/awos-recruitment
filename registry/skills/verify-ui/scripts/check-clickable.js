// check-clickable.js
// Checks whether elements are clickable by combining viewport bounds,
// visibility styles, and elementFromPoint hit-testing.
//
// Run it through the Playwright MCP with playwright:browser_run_code_unsafe:
//   1. Inject — defines checkClickable in the page:
//      code: async (page) => page.evaluate(`<the full text of this file>`)
//   2. Call:
//      code: async (page) => page.evaluate(
//        (opts) => checkClickable(opts),
//        { selectors: ['button'], scope: '[role="dialog"]' })
//
// Options:
//   selectors  array of CSS selectors to test, one result per selector (required)
//   scope      CSS selector to search within (defaults to the document)

function checkClickable({ selectors, scope } = {}) {
  if (!selectors || selectors.length === 0) {
    return { error: 'Provide a "selectors" array' };
  }

  const scopeEl = scope ? document.querySelector(scope) : document.documentElement;
  if (!scopeEl) {
    return { error: `Scope element not found: ${scope}` };
  }

  const viewport = { width: window.innerWidth, height: window.innerHeight };

  function test(element) {
    const rect = element.getBoundingClientRect();

    // Zero dimensions
    if (rect.width === 0 || rect.height === 0) {
      return { clickable: false, reason: "element has zero dimensions", blocked_by: null };
    }

    // Outside viewport
    if (
      rect.bottom < 0 ||
      rect.top > viewport.height ||
      rect.right < 0 ||
      rect.left > viewport.width
    ) {
      const axis = rect.top > viewport.height || rect.bottom < 0 ? "y" : "x";
      const coord = axis === "y" ? Math.round(rect.top) : Math.round(rect.left);
      const limit = axis === "y" ? viewport.height : viewport.width;
      return {
        clickable: false,
        reason: `element is outside viewport (${axis}: ${coord}, viewport ${axis === "y" ? "height" : "width"}: ${limit})`,
        blocked_by: null,
      };
    }

    // Visibility checks (only the four properties the skill permits)
    const cs = getComputedStyle(element);
    if (cs.display === "none")
      return { clickable: false, reason: "display: none", blocked_by: null };
    if (cs.visibility === "hidden")
      return { clickable: false, reason: "visibility: hidden", blocked_by: null };
    if (cs.opacity === "0")
      return { clickable: false, reason: "opacity: 0", blocked_by: null };
    if (cs.pointerEvents === "none")
      return { clickable: false, reason: "pointer-events: none", blocked_by: null };

    // Hit-test from center
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const topEl = document.elementFromPoint(cx, cy);

    if (!topEl) {
      return { clickable: false, reason: "elementFromPoint returned null", blocked_by: null };
    }

    if (element === topEl || element.contains(topEl)) {
      return { clickable: true, reason: "elementFromPoint returns self" };
    }

    // Covered by something else
    const tag = topEl.tagName.toLowerCase();
    const cls =
      topEl.className && typeof topEl.className === "string"
        ? "." + topEl.className.split(" ").filter(Boolean)[0]
        : "";
    return {
      clickable: false,
      reason: "covered by another element",
      blocked_by: `${tag}${cls}`,
    };
  }

  const results = [];

  for (const sel of selectors) {
    const el = scopeEl.querySelector(sel);
    if (!el) {
      results.push({
        selector: sel,
        text: null,
        clickable: false,
        reason: `element not found within scope`,
        blocked_by: null,
      });
      continue;
    }

    const verdict = test(el);
    results.push({
      selector: sel,
      text: (el.textContent || "").trim().substring(0, 50),
      ...verdict,
    });
  }

  return { results };
}
