// check-visibility-transition.js
// 3-stage visibility transition observation.
// Stage 1: setupVisibilityTransition() — installs MutationObserver, records initial state
// Stage 2: Agent performs click via Playwright native click (page.locator().click())
// Stage 3: collectVisibilityTransition() — waits for expected sequence and returns results
//
// Run it through the Playwright MCP with playwright:browser_run_code_unsafe:
//   1. Inject — defines both functions in the page:
//      code: async (page) => page.evaluate(`<the full text of this file>`)
//   2. Setup:
//      code: async (page) => page.evaluate(
//        (opts) => setupVisibilityTransition(opts),
//        { target: '.spinner', scope: '[role="dialog"]', expected: [false, true, false], timeout: 5000 })
//   3. Click:
//      code: async (page) => page.locator('.submit-button').click()
//   4. Collect:
//      code: async (page) => page.evaluate(() => collectVisibilityTransition())

function setupVisibilityTransition({
  target: targetSelector,
  scope,
  expected = [false, true, false],
  timeout = 5000,
} = {}) {
  if (!targetSelector) {
    return { error: 'Provide a "target" selector for the element to observe' };
  }

  const scopeEl = scope
    ? document.querySelector(scope)
    : document.documentElement;
  if (!scopeEl) {
    return { error: `Scope element not found: ${scope}` };
  }

  function isVisible(el) {
    if (!el || !el.isConnected) return false;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || cs.opacity === "0")
      return false;
    const rect = el.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  let targetEl = scopeEl.querySelector(targetSelector);
  const sequence = [isVisible(targetEl)];

  const observer = new MutationObserver(() => {
    targetEl = scopeEl.querySelector(targetSelector);
    const currentlyVisible = isVisible(targetEl);
    const lastRecorded = sequence[sequence.length - 1];
    if (currentlyVisible !== lastRecorded) {
      sequence.push(currentlyVisible);
    }
  });

  observer.observe(scopeEl, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["style", "class", "hidden", "aria-hidden", "data-state", "open"],
  });

  window.__visTransition = {
    observer, sequence, expected, targetSelector, scopeEl, isVisible,
    startTime: Date.now(), timeout,
  };

  return { ready: true, initialVisible: sequence[0] };
}

async function collectVisibilityTransition() {
  const ctx = window.__visTransition;
  if (!ctx) return { error: 'Call setupVisibilityTransition first' };

  const { observer, sequence, expected, targetSelector, timeout, startTime } = ctx;

  // The MutationObserver records every transition as it happens, so this
  // interval only controls how soon this function notices the sequence is
  // already complete — it cannot miss a transition. 100ms keeps the wasted
  // wait below what a person would notice, at ~10 no-op comparisons per
  // second, which is nothing next to the multi-second timeout it runs under.
  const POLL_INTERVAL_MS = 100;

  const remaining = Math.max(0, timeout - (Date.now() - startTime));
  const deadline = Date.now() + remaining;
  await new Promise((resolve) => {
    const check = setInterval(() => {
      if (
        JSON.stringify(sequence) === JSON.stringify(expected) ||
        Date.now() >= deadline
      ) {
        clearInterval(check);
        resolve();
      }
    }, POLL_INTERVAL_MS);
  });

  observer.disconnect();
  delete window.__visTransition;

  const matches = JSON.stringify(sequence) === JSON.stringify(expected);
  const duration = Date.now() - startTime;

  return {
    selector: targetSelector,
    sequence,
    expected,
    matches,
    duration,
    reason: matches
      ? describeTransition(expected)
      : `timeout: ${describeFailure(sequence, expected, timeout)}`,
  };
}

function describeTransition(seq) {
  const key = JSON.stringify(seq);
  if (key === "[false,true,false]") return "element appeared then disappeared as expected";
  if (key === "[true,false,true]") return "element hid then reappeared as expected";
  if (key === "[false,true]") return "element appeared and stayed visible as expected";
  if (key === "[true,false]") return "element disappeared and stayed hidden as expected";
  return `visibility sequence ${key} matched expected`;
}

function describeFailure(actual, expected, timeout) {
  const last = actual[actual.length - 1];
  if (actual.length === 1 && !actual[0] && expected[1] === true) {
    return `element never became visible within ${timeout}ms`;
  }
  if (actual.length === 1 && actual[0] && expected[1] === false) {
    return `element never became hidden within ${timeout}ms`;
  }
  if (actual.length === 2 && actual[1] && expected.length === 3 && !expected[2]) {
    return `element appeared but never disappeared within ${timeout}ms`;
  }
  if (actual.length === 2 && !actual[1] && expected.length === 3 && expected[2]) {
    return `element disappeared but never reappeared within ${timeout}ms`;
  }
  return `expected sequence ${JSON.stringify(expected)} but got ${JSON.stringify(actual)} within ${timeout}ms`;
}
