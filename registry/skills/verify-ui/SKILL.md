---
name: verify-ui
context: fork
argument-hint: "<feature or acceptance criteria to verify> <route or URL> <app base URL>"
description: >
  Verifies a web UI in a running browser by measuring the live DOM with bundled scripts — visibility, clickability, alignment, overflow, and the state a click leaves behind — instead of reading screenshots. Use when a change to a web UI needs verifying in the running app, when a UI bug is reported (something on screen is missing, misplaced, clipped, or unclickable), or when acceptance criteria describe on-screen behaviour. Prefer this over writing custom Playwright page.evaluate code.
---

# Verify UI

Verify: $ARGUMENTS

This skill runs in its own context and never sees the conversation that
launched it, so the line above is the whole brief. If it is empty, or names no
feature, route, or URL, say what is missing and stop — there is no page to open
and guessing at one wastes a browser session.

## The one tool

Every browser action goes through `playwright:browser_run_code_unsafe`. Its
`code` argument is an `async (page) => ...` function, and every `page.*` call in
this document belongs inside that function:

```
playwright:browser_run_code_unsafe({
  code: `async (page) => page.locator('.submit-button').click()`
})
```

Stick to this one tool and this one vocabulary throughout. `page.*` calls do not
exist in the other Playwright MCP tools, so mixing them produces "not a
function" errors.

Follow this process for every verification. Use the bundled scripts — do not
write custom `page.evaluate` code unless the scripts cannot answer the question.

## Step 1: Understand what to verify
Read the minimum source code to identify:
1. How to reach the feature (route, buttons to click)
2. Key selectors (CSS classes, roles, test-ids)
3. Expected layout rules from CSS (flex direction, gaps, alignment)

Stop once you have those three. Exploring the full component tree costs a lot of
context and rarely changes which selectors you measure.

Target elements by CSS selector, role, or text. A `[ref=...]` value belongs to
the snapshot that produced it and does not resolve anywhere else, so if you have
a ref, map it back to a class, role, or text selector before using it.

## Step 2: Navigate to the feature
- Use `page.locator('selector').click()` for all interactions
- You already know the selectors from Step 1, so go straight to clicking and
  measuring rather than snapshotting the page to "see" it

## Step 3: Load and run verification scripts
For EVERY measurement, follow this exact sequence:

### After-action state checks (the most common check — start here)
This is a 3-stage check: setup observer, perform click with Playwright, collect results.
1. Read: `Read ${CLAUDE_SKILL_DIR}/scripts/check-after-action.js`
2. Inject into page: `page.evaluate(scriptContent)`
3. Setup: `page.evaluate((opts) => setupAfterAction(opts), { scope: '[role="dialog"]', expect: [{ selector: '.success-message', visible: true }, { selector: '.loading-spinner', visible: false }], timeout: 5000 })`
4. Click with Playwright: `page.locator('.submit-button').click()`
5. Collect: `page.evaluate(() => collectAfterAction())`
6. Check overall `pass` and each result's `reason`

Use this for: selection state changes, popup open/close, tab switching,
form submission results — any click that should change the UI permanently.
Use checkVisibilityTransition instead when tracking temporary elements
(spinners, toasts, animations).

### Alignment checks
1. Read the script: `Read ${CLAUDE_SKILL_DIR}/scripts/check-alignment.js`
2. Inject into page: `page.evaluate(scriptContent)` where scriptContent is the 
   full file you just read
3. Call: `page.evaluate(() => checkAlignment({ containerSelector: '...', scopeSelector: '...' }))`
4. Interpret the result: check `behavior`, `alignment`, `gaps.uniform`, `gaps.value`

Options:
- `containerSelector`: the container whose children to compare
- `selectors`: compare these specific elements instead of a container's children
- `scopeSelector`: search within this element rather than the whole document
- `tolerance`: how many pixels apart two edges can sit and still count as
  aligned (default: 1). Browsers report fractional pixels, so exact equality
  would flag an aligned row as `behavior: "unknown"`. Raise it to 2-3 for
  layouts inside a CSS transform; drop it to 0 to assert exact pixel equality.

A `behavior: "unknown"` result reports the `tolerance` it used — before calling
the layout broken, re-run with a larger one to see whether the elements were
merely a fraction of a pixel apart.

### Clickability checks  
1. Read: `Read ${CLAUDE_SKILL_DIR}/scripts/check-clickable.js`
2. Inject into page
3. Call: `page.evaluate(() => checkClickable({ selectors: [...], scope: '...' }))`
4. Check each result's `clickable` and `reason`

### Visibility transition checks
This is a 3-stage check: setup observer, perform click with Playwright, collect results.
1. Read: `Read ${CLAUDE_SKILL_DIR}/scripts/check-visibility-transition.js`
2. Inject into page: `page.evaluate(scriptContent)`
3. Setup: `page.evaluate((opts) => setupVisibilityTransition(opts), { target: '.spinner', scope: '[role="dialog"]', expected: [false, true, false], timeout: 5000 })`
4. Click with Playwright: `page.locator('.submit-button').click()`
5. Collect: `page.evaluate(() => collectVisibilityTransition())`
6. Check `matches` and `reason`

### Container inventory checks
Use this after opening a popover, dialog, or dropdown to discover everything inside in one call
instead of writing custom discovery code each time.
1. Read: `Read ${CLAUDE_SKILL_DIR}/scripts/check-inventory.js`
2. Inject into page
3. Call: `page.evaluate(() => checkInventory({
     scope: '[data-example]', // e.g.: [data-popover-content], [data-radix-popper-content-wrapper], [role="dialog"]
     include: ['button', '[role="option"]', '[role="radio"]', '[role="group"]']
   }))`
4. Inspect `summary` for counts, `sections` for labeled groups, `scrollState` for scroll info,
   and `elements` for the full list with text/role/ariaState/visible/inViewport per element.

Options:
- `scope` (required): CSS selector for the container to inventory
- `include`: array of selectors to search for (defaults to all common interactive roles)
- `exclude`: array of selectors to skip
- `maxDepth`: limit DOM traversal depth

### Overflow and reachability checks
Use this to check whether a container or its children overflow the viewport,
whether footer content is clipped, and whether interactive elements are still reachable.
1. Read: `Read ${CLAUDE_SKILL_DIR}/scripts/check-overflow.js`
2. Inject into page
3. Call: `page.evaluate(() => checkOverflow({
     scope: '[data-side]',
     checkFooter: true
   }))`
4. Check `summary` for the quick verdict (`overflows`, `scrollable`, `footerClipped`,
   `unreachableCount`), `overflow`/`overflowPx` for directional detail, `footer` for
   last-child clipping, and `unreachable` for any interactive elements that can't be clicked.

Options:
- `scope` (required): CSS selector for the container to check
- `checkFooter`: check if the last visible child is clipped (default: true)
- `checkInteractive`: hit-test all interactive elements for reachability (default: true)
- `margin`: pixel tolerance for overflow detection (default: 0)
- `maxDepth`: how many levels down to look for clipped descendants (default: 5).
  Five levels reaches the panels, sections, and controls a user can see; raise
  it only when the tree under test is genuinely deeper.

### How to inject scripts
Scripts live on disk, NOT accessible from the browser. To inject:
1. Use the Read tool: `Read ${CLAUDE_SKILL_DIR}/scripts/check-alignment.js`
   `${CLAUDE_SKILL_DIR}` expands to this skill's own directory, so the path
   resolves wherever the skill is installed and whatever the current working
   directory is. Write it exactly like that — do not substitute a literal path.
2. The file content is now in YOUR context (not the browser's)
3. Inject via: `page.evaluate(fileContent)` — this defines the function in browser scope
4. Then call: `page.evaluate(() => checkAlignment({...}))`
Do not use fetch() or import() to load scripts — the browser cannot read local files

## Step 4: Compile results
Report every check in a Markdown table with the columns "Elements", "Check", "Result", "Details", "Suggested fix" for instance:
```
| Elements | Check | Result | Details | Suggested fix |
|----------|-------|--------|---------|---------------|
| .search-input | visible | ✅ | Visible at the very top on the search form | N/A |
| .search-input | clickable | ✅ | elementFromPoint returns self | N/A |
| .dropdown | appears on focus | ❌ | MutationObserver: element never became visible within 3s | Add visibility state change on search input focus |
```
### Important Notes Towards Details And Summaries
Instead of providing numeric information, explain what is going on semantically. Imagine that user does not see the skill at all and you have to explain to him being in complete blindness

## General rules
- For clicking elements, use Playwright's native click via page.locator('selector').click() rather than dispatchEvent or element.click() from page.evaluate — components often listen for real pointer events, and a synthetic event silently does nothing.
- For selector, prioritize text which element contains or accessibility attributes (e.g. aria-role)
- To make selection more precise, instead of selecting element on the whole page, first extract feature box element from page (use text feature contains, classes, test-ids, consider mixing those approaches if you struggle to select single item, example: .locator('\[role="form"\]:has-text("Register Account")')), then use locator from feature element instead of page
- For tab switching, radio selection, checkbox filling, dropdown element picking and all other user interactions use native clicks: .locator(\<selector\>).click()
- use .fill() for text input and .press() or page.keyboard.press() for key presses, do not edit DOM value field directly
- avoid gathering getComputedStyle information other than about visibility/opacity: that is redundant, getBoundingClientRect provides full data about shape and positioning

## Custom scripts
Write custom `page.evaluate` code only once the scripts above have been tried and still leave the question open.

## Navigation efficiency
- Measuring beats looking: go straight to clicking and measuring with the
  scripts above rather than snapshotting to orient yourself.
- When you need to inspect a specific area of the page, use page.locator('css-selector').evaluate()
- If you genuinely don't know what is on the page — an unknown bug with no code
  context — `playwright:browser_snapshot` is the one exception to the single-tool
  rule. Use it to discover structure, then translate what you find into CSS,
  role, or text selectors and measure with those; the refs it returns are not
  usable anywhere else.

## What skill does not do
- Skill does not verify visual appearance (colors, fonts, spacing and contrast aesthetics), it verifies only if the feature elements behave as it planned by spec and codebase
- Skill does not test cross-browser behavior and uses only Playwright Chromium browser
- Skill does not verify accessibility features use different skill for that
- Skill avoids using screenshots and fallbacks to them only in case of low confidence after usage of tools
</content>
