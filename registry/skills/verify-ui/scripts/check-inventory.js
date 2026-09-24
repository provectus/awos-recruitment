// check-inventory.js
// Returns a structured map of what's inside a scoped container:
// interactive elements (buttons, inputs, links) with their text, roles,
// aria states, and the container's scroll state.
//
// Run it through the Playwright MCP with playwright:browser_run_code_unsafe:
//   1. Inject — defines checkInventory in the page:
//      code: async (page) => page.evaluate(`<the full text of this file>`)
//   2. Call:
//      code: async (page) => page.evaluate(
//        (opts) => checkInventory(opts),
//        { scope: '[data-radix-popper-content-wrapper]' })
//
// Options:
//   scope     CSS selector for the container to inventory (required)
//   include   array of selectors to search for (defaults to all interactive roles)
//   exclude   array of selectors to skip
//   maxDepth  measure the container's nesting depth, up to this many levels

function checkInventory({ scope, include, exclude, maxDepth } = {}) {
  if (!scope) {
    return { error: 'Provide a "scope" selector' };
  }

  const scopeEl = document.querySelector(scope);
  if (!scopeEl) {
    return { error: `Scope element not found: ${scope}` };
  }

  // Default interactive selectors when include is not provided
  const defaultInclude = [
    "button",
    "a[href]",
    "input",
    "select",
    "textarea",
    '[role="button"]',
    '[role="link"]',
    '[role="option"]',
    '[role="radio"]',
    '[role="checkbox"]',
    '[role="switch"]',
    '[role="tab"]',
    '[role="menuitem"]',
    '[role="menuitemcheckbox"]',
    '[role="menuitemradio"]',
    '[role="slider"]',
    '[role="spinbutton"]',
    '[role="combobox"]',
    '[role="searchbox"]',
    '[role="listbox"]',
  ];

  const selectors = include && include.length ? include : defaultInclude;
  const excludeSet = new Set(exclude || []);

  const viewport = { width: window.innerWidth, height: window.innerHeight };
  const scopeRect = scopeEl.getBoundingClientRect();

  // --- Collect all matching elements, deduped ---
  const seen = new Set();
  const elements = [];

  for (const sel of selectors) {
    if (excludeSet.has(sel)) continue;
    const matches = scopeEl.querySelectorAll(sel);
    for (const el of matches) {
      if (seen.has(el)) continue;
      seen.add(el);
      elements.push(el);
    }
  }

  // --- Build element descriptors ---
  function describeElement(el) {
    const rect = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute("role") || implicitRole(el);
    const text = (el.textContent || "").trim().substring(0, 80);

    // Collect all aria-* attributes
    const ariaState = {};
    for (const attr of el.attributes) {
      if (attr.name.startsWith("aria-")) {
        ariaState[attr.name] = attr.value;
      }
    }

    // Add checked/disabled/selected for native form elements
    if (el.disabled !== undefined && el.disabled) ariaState["disabled"] = "true";
    if (el.checked !== undefined && el.checked) ariaState["checked"] = "true";

    // Visibility
    const visible =
      cs.display !== "none" &&
      cs.visibility !== "hidden" &&
      cs.opacity !== "0" &&
      rect.width > 0 &&
      rect.height > 0;

    // Within viewport
    const inViewport =
      rect.top < viewport.height &&
      rect.bottom > 0 &&
      rect.left < viewport.width &&
      rect.right > 0;

    // Build a usable selector
    const selector = buildSelector(el);

    return {
      selector,
      tag,
      role,
      text: text || null,
      ariaState: Object.keys(ariaState).length ? ariaState : null,
      visible,
      inViewport: visible ? inViewport : false,
      rect: {
        top: Math.round(rect.top),
        left: Math.round(rect.left),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      },
    };
  }

  function implicitRole(el) {
    const tag = el.tagName.toLowerCase();
    const type = el.getAttribute("type");
    if (tag === "button") return "button";
    if (tag === "a" && el.hasAttribute("href")) return "link";
    if (tag === "input" && type === "checkbox") return "checkbox";
    if (tag === "input" && type === "radio") return "radio";
    if (tag === "input" && type === "range") return "slider";
    if (tag === "input") return "textbox";
    if (tag === "select") return "combobox";
    if (tag === "textarea") return "textbox";
    return null;
  }

  function buildSelector(el) {
    if (el.id) return `#${el.id}`;
    const dataTestId = el.getAttribute("data-testid");
    if (dataTestId) return `[data-testid="${dataTestId}"]`;
    const dataTestIdAlt = el.getAttribute("data-test-id");
    if (dataTestIdAlt) return `[data-test-id="${dataTestIdAlt}"]`;
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute("role");
    const text = (el.textContent || "").trim().substring(0, 30);
    if (role) {
      const pressed = el.getAttribute("aria-pressed");
      const selected = el.getAttribute("aria-selected");
      const label = el.getAttribute("aria-label");
      if (label) return `${tag}[role="${role}"][aria-label="${label}"]`;
      if (pressed !== null)
        return `${tag}[role="${role}"][aria-pressed="${pressed}"]:text("${text}")`;
      if (selected !== null)
        return `${tag}[role="${role}"][aria-selected="${selected}"]:text("${text}")`;
      if (text) return `${tag}[role="${role}"]:text("${text}")`;
      return `${tag}[role="${role}"]`;
    }
    const cls =
      el.className && typeof el.className === "string"
        ? "." + el.className.split(" ").filter(Boolean).slice(0, 2).join(".")
        : "";
    if (text) return `${tag}${cls}:text("${text}")`;
    return `${tag}${cls}`;
  }

  // --- Detect groups/sections ---
  const groupSelectors = [
    '[role="group"]',
    '[role="radiogroup"]',
    '[role="tablist"]',
    '[role="listbox"]',
    '[role="menu"]',
    "fieldset",
  ];

  const sections = [];
  for (const gSel of groupSelectors) {
    const groups = scopeEl.querySelectorAll(gSel);
    for (const g of groups) {
      const labelledBy = g.getAttribute("aria-labelledby");
      const resolvedLabelledBy = labelledBy
        ? labelledBy.split(/\s+/).map(id => document.getElementById(id)?.textContent?.trim()).filter(Boolean).join(" ")
        : null;
      const label =
        g.getAttribute("aria-label") ||
        resolvedLabelledBy ||
        (g.querySelector("legend") || {}).textContent ||
        null;
      const role = g.getAttribute("role") || g.tagName.toLowerCase();
      const childCount = g.querySelectorAll(
        selectors.join(",")
      ).length;
      sections.push({
        role,
        label: label ? label.trim().substring(0, 60) : null,
        childCount,
        selector: buildSelector(g),
      });
    }
  }

  // --- Scroll state ---
  function getScrollState(el) {
    const cs = getComputedStyle(el);
    const overflowY = cs.overflowY;
    const overflowX = cs.overflowX;
    const scrollableY =
      (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") &&
      el.scrollHeight > el.clientHeight;
    const scrollableX =
      (overflowX === "auto" || overflowX === "scroll" || overflowX === "overlay") &&
      el.scrollWidth > el.clientWidth;

    if (!scrollableY && !scrollableX) return null;

    return {
      scrollableY,
      scrollableX,
      scrollTop: Math.round(el.scrollTop),
      scrollLeft: Math.round(el.scrollLeft),
      scrollHeight: el.scrollHeight,
      scrollWidth: el.scrollWidth,
      clientHeight: el.clientHeight,
      clientWidth: el.clientWidth,
      atTop: el.scrollTop <= 0,
      atBottom: el.scrollTop + el.clientHeight >= el.scrollHeight - 1,
      atLeft: el.scrollLeft <= 0,
      atRight: el.scrollLeft + el.clientWidth >= el.scrollWidth - 1,
    };
  }

  // Check the scope element and its direct children for scrollability
  const scrollState = getScrollState(scopeEl);
  let scrollableChild = null;
  if (!scrollState) {
    for (const child of scopeEl.children) {
      const childScroll = getScrollState(child);
      if (childScroll) {
        scrollableChild = {
          selector: buildSelector(child),
          ...childScroll,
        };
        break;
      }
    }
  }

  // --- Detect depth limit ---
  let depth = 0;
  if (maxDepth) {
    let current = scopeEl;
    function walk(el, d) {
      if (d > depth) depth = d;
      if (d >= maxDepth) return;
      for (const child of el.children) walk(child, d + 1);
    }
    walk(scopeEl, 0);
  }

  // --- Summary counts ---
  const described = elements.map(describeElement);
  const visibleCount = described.filter((e) => e.visible).length;
  const inViewportCount = described.filter((e) => e.inViewport).length;

  return {
    scope,
    scopeRect: {
      top: Math.round(scopeRect.top),
      left: Math.round(scopeRect.left),
      width: Math.round(scopeRect.width),
      height: Math.round(scopeRect.height),
      bottom: Math.round(scopeRect.bottom),
      right: Math.round(scopeRect.right),
    },
    viewport,
    summary: {
      total: described.length,
      visible: visibleCount,
      inViewport: inViewportCount,
      hidden: described.length - visibleCount,
      sections: sections.length,
    },
    scrollState: scrollState || scrollableChild || null,
    sections,
    elements: described,
  };
}
