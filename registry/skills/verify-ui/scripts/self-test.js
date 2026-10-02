// self-test.js
// Smoke test for the other check scripts in this directory. It builds a small
// fixture in the live page, runs every check against it, asserts the results,
// and removes the fixture again — so it can run against any page without
// touching that page's own DOM.
//
// Run it through the Playwright MCP with playwright:browser_run_code_unsafe,
// after injecting the scripts under test:
//   code: async (page) => {
//     for (const f of [afterActionSrc, alignmentSrc, clickableSrc,
//                      inventorySrc, overflowSrc, visibilitySrc, selfTestSrc]) {
//       await page.evaluate(f);
//     }
//     return page.evaluate(() => runSelfTest());
//   }
//
// Returns { total, passed, failed, failures, checks }. `failed: 0` means the
// scripts behave as this skill documents. Run it after changing any of them,
// and when a check reports something surprising on a real page — if the self
// test still passes, the surprise is in the page, not in the script.

// Constants live inside their function on purpose. These files are injected by
// evaluating their source text in the page under test, so anything declared at
// the top level lands in that page's own scope. Keeping names inside the
// functions means injecting this script cannot shadow or collide with whatever
// the application already defines.

function vuiBuildFixture() {
  // The fixture sits above everything else so that elementFromPoint hit tests
  // resolve to fixture elements, not to whatever the host page renders.
  const FIXTURE_Z_INDEX = 2147483647;

  const host = document.createElement("div");
  host.id = "vui-fixture";
  host.style.cssText = [
    "position:fixed",
    "top:0",
    "left:0",
    "width:400px",
    "height:320px",
    "margin:0",
    "background:#fff",
    `z-index:${FIXTURE_Z_INDEX}`,
  ].join(";");

  // A flex-style row of three equal boxes. The middle one is nudged down by a
  // fraction of a pixel, which is what a border, a transform, or a fractional
  // font metric does to a real row — the row is still a row to a user.
  const rowItems = [0, 100, 200]
    .map(
      (left, i) =>
        `<div class="vui-item" style="position:absolute;left:${left}px;top:0;` +
        `width:80px;height:40px;${i === 1 ? "transform:translateY(0.4px);" : ""}">` +
        `Item ${i + 1}</div>`,
    )
    .join("");

  // Overflow case: a box hanging 100px past the right edge of the viewport.
  const overflowLeft = window.innerWidth - 100;

  host.innerHTML = `
    <div id="vui-row" style="position:absolute;top:10px;left:10px;width:300px;height:40px;">
      ${rowItems}
    </div>

    <button id="vui-btn-plain" style="position:absolute;top:70px;left:10px;width:120px;height:30px;">
      Plain
    </button>
    <button id="vui-btn-covered" style="position:absolute;top:110px;left:10px;width:120px;height:30px;">
      Covered
    </button>
    <div id="vui-cover" style="position:absolute;top:110px;left:10px;width:120px;height:30px;background:#eee;"></div>

    <div id="vui-dialog" role="dialog" style="position:absolute;top:150px;left:10px;width:300px;height:70px;">
      <div role="radiogroup" aria-label="Plan">
        <span role="radio" aria-checked="true" style="display:inline-block;width:60px;height:20px;">Free</span>
        <span role="radio" aria-checked="false" style="display:inline-block;width:60px;height:20px;">Pro</span>
      </div>
      <button id="vui-dialog-save" style="width:60px;height:20px;">Save</button>
    </div>

    <div id="vui-aa" style="position:absolute;top:230px;left:10px;width:300px;height:30px;">
      <button id="vui-aa-submit" style="width:80px;height:24px;">Submit</button>
    </div>

    <div id="vui-vis" style="position:absolute;top:270px;left:10px;width:300px;height:30px;">
      <div id="vui-spinner" style="display:none;width:20px;height:20px;">Loading</div>
    </div>

    <div id="vui-overflow" style="position:fixed;top:0;left:${overflowLeft}px;width:200px;height:20px;"></div>
  `;

  document.body.appendChild(host);

  // Submitting reveals a success message — the permanent state change that
  // check-after-action.js is built to observe.
  host.querySelector("#vui-aa-submit").addEventListener("click", () => {
    const ok = document.createElement("div");
    ok.className = "vui-success";
    ok.style.cssText = "width:100px;height:20px;";
    ok.textContent = "Saved";
    host.querySelector("#vui-aa").appendChild(ok);
  });

  return () => host.remove();
}

async function runSelfTest() {
  // How long the two observer cases wait. Their show/hide cycle takes ~150ms;
  // this leaves room for a slow frame without making a real failure slow to
  // report.
  const TRANSITION_TIMEOUT_MS = 2000;

  const checks = [];
  const record = (name, ok, detail) => checks.push({ name, ok, detail });
  const expect = (name, ok, detail) => record(name, Boolean(ok), detail);

  const cleanup = vuiBuildFixture();

  try {
    // --- Alignment: sub-pixel drift must not hide a row -------------------
    const row = checkAlignment({ containerSelector: "#vui-row" });
    expect(
      "alignment: a row with 0.4px vertical drift is still a row",
      row.behavior === "row",
      `behavior=${row.behavior} tolerance=${row.tolerance}`,
    );
    expect(
      "alignment: that row reports top-aligned",
      Array.isArray(row.alignment) && row.alignment.includes("top-aligned"),
      `alignment=${JSON.stringify(row.alignment)}`,
    );
    expect(
      "alignment: its 20px gaps read as uniform",
      row.gaps && row.gaps.uniform === true && row.gaps.value === "20px",
      `gaps=${JSON.stringify(row.gaps)}`,
    );

    // tolerance: 0 restores strict float equality, which is what made the
    // same row unreadable before the tolerance option existed. If this ever
    // starts reporting "row", the tolerance is no longer doing anything.
    const strict = checkAlignment({ containerSelector: "#vui-row", tolerance: 0 });
    expect(
      "alignment: tolerance 0 is strict again",
      strict.behavior !== "row",
      `behavior=${strict.behavior}`,
    );

    // --- Clickability -----------------------------------------------------
    const clickable = checkClickable({
      selectors: ["#vui-btn-plain", "#vui-btn-covered", "#vui-missing"],
      scope: "#vui-fixture",
    });
    const [plain, covered, missing] = clickable.results;
    expect("clickable: an unobstructed button is clickable", plain.clickable === true, plain.reason);
    expect(
      "clickable: a covered button reports what covers it",
      covered.clickable === false && covered.reason === "covered by another element",
      `${covered.reason} / blocked_by=${covered.blocked_by}`,
    );
    expect(
      "clickable: a missing selector is reported, not thrown",
      missing.clickable === false && /not found/.test(missing.reason),
      missing.reason,
    );

    // --- Overflow ---------------------------------------------------------
    const overflow = checkOverflow({ scope: "#vui-overflow", checkInteractive: false });
    expect(
      "overflow: a box past the right edge is flagged",
      overflow.summary.overflows === true && overflow.overflow.right === true,
      `overflowPx.right=${overflow.overflowPx.right}`,
    );
    expect(
      "overflow: the reported overshoot matches the fixture's 100px",
      Math.abs(overflow.overflowPx.right - 100) <= 1,
      `overflowPx.right=${overflow.overflowPx.right}`,
    );
    expect(
      "overflow: the scan depth is reported",
      overflow.maxDepth === 5,
      `maxDepth=${overflow.maxDepth}`,
    );

    // --- Inventory --------------------------------------------------------
    const inventory = checkInventory({ scope: "#vui-dialog" });
    expect(
      "inventory: finds both radios and the button",
      inventory.summary.total === 3,
      `total=${inventory.summary.total}`,
    );
    expect(
      "inventory: names the labelled radiogroup",
      inventory.sections.some((s) => s.label === "Plan" && s.role === "radiogroup"),
      `sections=${JSON.stringify(inventory.sections)}`,
    );
    expect(
      "inventory: carries aria state through",
      inventory.elements.some((e) => e.ariaState && e.ariaState["aria-checked"] === "true"),
      "expected one aria-checked=true radio",
    );

    // --- After-action state ----------------------------------------------
    setupAfterAction({
      scope: "#vui-aa",
      expect: [{ selector: ".vui-success", visible: true }],
      timeout: TRANSITION_TIMEOUT_MS,
    });
    // A synthetic click is fine here because this fixture's own listener is
    // what reacts to it. Real components often need Playwright's native click,
    // which is why the skill tells you to click through page.locator().
    document.querySelector("#vui-aa-submit").click();
    const afterAction = await collectAfterAction();
    expect(
      "after-action: sees the success message appear",
      afterAction.pass === true,
      afterAction.results && afterAction.results[0] && afterAction.results[0].reason,
    );

    // --- Visibility transition -------------------------------------------
    setupVisibilityTransition({
      target: "#vui-spinner",
      scope: "#vui-vis",
      expected: [false, true, false],
      timeout: TRANSITION_TIMEOUT_MS,
    });
    const spinner = document.querySelector("#vui-spinner");
    spinner.style.display = "block";
    setTimeout(() => {
      spinner.style.display = "none";
    }, 150);
    const transition = await collectVisibilityTransition();
    expect(
      "visibility: records the hidden -> shown -> hidden cycle",
      transition.matches === true,
      `sequence=${JSON.stringify(transition.sequence)} reason=${transition.reason}`,
    );
  } catch (error) {
    record("self-test threw", false, String((error && error.stack) || error));
  } finally {
    cleanup();
  }

  const failures = checks.filter((c) => !c.ok);
  return {
    total: checks.length,
    passed: checks.length - failures.length,
    failed: failures.length,
    failures,
    checks,
  };
}
