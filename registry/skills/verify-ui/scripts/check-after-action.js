// check-after-action.js
// 3-stage after-action state verification.
// Stage 1: setupAfterAction() — installs polling observer, returns handle
// Stage 2: Agent performs click via Playwright native click (page.locator().click())
// Stage 3: collectAfterAction() — waits for expected state and returns results
//
// Run it through the Playwright MCP with playwright:browser_run_code_unsafe:
//   1. Inject — defines both functions in the page:
//      code: async (page) => page.evaluate(`<the full text of this file>`)
//   2. Setup:
//      code: async (page) => page.evaluate(
//        (opts) => setupAfterAction(opts),
//        { scope: '[role="dialog"]', expect: [{ selector: '.success-message', visible: true }], timeout: 5000 })
//   3. Click:
//      code: async (page) => page.locator('.submit-button').click()
//   4. Collect:
//      code: async (page) => page.evaluate(() => collectAfterAction())

function setupAfterAction({ expect, scope, timeout = 5000 } = {}) {
  if (!expect || !expect.length) return { error: 'Provide an "expect" array' };

  const scopeEl = scope ? document.querySelector(scope) : document.documentElement;
  if (scope && !scopeEl) return { error: `Scope not found: ${scope}` };

  // Store on window so collectAfterAction can access it
  window.__afterAction = { expect, scope, scopeEl, timeout, startTime: Date.now() };
  return { ready: true };
}

async function collectAfterAction() {
  const ctx = window.__afterAction;
  if (!ctx) return { error: 'Call setupAfterAction first' };

  const { expect, scope, scopeEl, timeout, startTime } = ctx;

  function isVisible(el) {
    if (!el || !el.isConnected) return false;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || cs.opacity === "0") return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function findTargets(selector, text) {
    const all = [...scopeEl.querySelectorAll(selector)];
    if (!text) return all;
    return all.filter((el) => (el.textContent || "").includes(text));
  }

  function checkEntry(entry) {
    const wantVisible = entry.visible !== false;
    const matches = findTargets(entry.selector, entry.text);
    const anyVisible = matches.some((el) => isVisible(el));
    return wantVisible ? anyVisible : !anyVisible;
  }

  // Poll until expected state or timeout
  const remaining = Math.max(0, timeout - (Date.now() - startTime));
  const deadline = Date.now() + remaining;
  await new Promise((resolve) => {
    (function poll() {
      if (expect.every(checkEntry) || Date.now() >= deadline) return resolve();
      requestAnimationFrame(poll);
    })();
  });

  const duration = Date.now() - startTime;

  const results = expect.map((entry) => {
    const wantVisible = entry.visible !== false;
    const matches = findTargets(entry.selector, entry.text);
    const actualVisible = matches.some((el) => isVisible(el));
    const pass = actualVisible === wantVisible;

    const result = {
      selector: entry.selector,
      pass,
      expected: wantVisible ? "visible" : "hidden",
      actual: actualVisible ? "visible" : matches.length ? "hidden" : "not found",
    };

    if (entry.text) result.text = entry.text;

    if (pass) {
      result.reason = wantVisible
        ? entry.text
          ? `element containing "${entry.text}" is visible`
          : "element is visible"
        : entry.text
          ? `no visible element contains "${entry.text}"`
          : matches.length
            ? "element is hidden"
            : "element not found";
    } else {
      result.reason = wantVisible
        ? entry.text
          ? `no element matching "${entry.selector}" with text "${entry.text}" became visible within ${timeout}ms`
          : `element "${entry.selector}" did not become visible within ${timeout}ms`
        : entry.text
          ? `element "${entry.selector}" still shows "${entry.text}" after ${timeout}ms`
          : `element "${entry.selector}" still visible after ${timeout}ms`;
    }

    return result;
  });

  delete window.__afterAction;

  return {
    pass: results.every((r) => r.pass),
    duration,
    results,
  };
}
