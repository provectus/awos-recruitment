// check-alignment.js
// Detects layout behavior (row, column, line, v-line, grid) and verifies alignment.
//
// Run it through the Playwright MCP with playwright:browser_run_code_unsafe:
//   1. Inject — defines checkAlignment in the page:
//      code: async (page) => page.evaluate(`<the full text of this file>`)
//   2. Call:
//      code: async (page) => page.evaluate(
//        (opts) => checkAlignment(opts),
//        { containerSelector: '[role="tablist"]' })
//
// Options:
//   selectors         array of CSS selectors naming the elements to compare
//   containerSelector CSS selector for the container whose children to compare
//   scopeSelector     CSS selector to search within (defaults to the document)
//   tolerance         px slack for "same edge" and "same gap" (default 1)

function checkAlignment({
  selectors,
  containerSelector,
  scopeSelector,
  tolerance: toleranceOption,
} = {}) {
  // Browsers report getBoundingClientRect() as sub-pixel floats, so visually
  // aligned elements routinely differ by a fraction of a pixel: a 1px border,
  // a CSS transform, a fractional font metric, or a non-integer device pixel
  // ratio is enough. Comparing those floats for strict equality reports a
  // perfectly aligned flex row as unaligned. 1px is the smallest difference a
  // user can actually see, so treat anything at or below it as the same
  // position. Raise it (2-3) for layouts scaled by a transform; lower it to 0
  // only to assert exact pixel equality.
  const DEFAULT_TOLERANCE_PX = 1;
  const tolerance = toleranceOption ?? DEFAULT_TOLERANCE_PX;

  // --- Resolve scope ---
  const scopeEl = scopeSelector
    ? document.querySelector(scopeSelector)
    : document.documentElement;
  if (scopeSelector && !scopeEl) {
    return { error: `Scope not found: ${scopeSelector}` };
  }

  // --- Helper: find container (handles scope === container case) ---
  const findInScope = (selector) => {
    if (!selector) return null;
    if (scopeEl !== document.documentElement && scopeEl.matches(selector)) return scopeEl;
    return scopeEl.querySelector(selector);
  };

  // --- Resolve elements and container ---
  let elements = [];
  let containerEl = null;

  if (selectors && selectors.length) {
    for (const sel of selectors) {
      const el = findInScope(sel);
      if (!el) return { error: `Element not found: ${sel}` };
      elements.push(el);
    }
    if (containerSelector) {
      containerEl = findInScope(containerSelector);
    }
  } else if (containerSelector) {
    containerEl = findInScope(containerSelector);
    if (!containerEl) return { error: `Container not found: ${containerSelector}` };
    elements = Array.from(containerEl.children).filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    });
  } else {
    return { error: "Provide selectors or containerSelector" };
  }

  if (elements.length === 0) {
    return { count: 0, error: "No visible elements found" };
  }

  // --- Gather rects and container rect ---
  const rects = elements.map((el) => el.getBoundingClientRect());
  const refEl = containerEl || elements[0].parentElement;
  const containerRect = refEl ? refEl.getBoundingClientRect() : null;

  // ============================================================
  // Helpers
  // ============================================================

  const yOf = (r, edge) =>
    edge === "top" ? r.top : edge === "bottom" ? r.bottom : r.top + r.height / 2;

  const xOf = (r, edge) =>
    edge === "left" ? r.left : edge === "right" ? r.right : r.left + r.width / 2;

  // Spread of a numeric list — how far apart its extremes are.
  const spread = (arr) => Math.max(...arr) - Math.min(...arr);

  // "All the same" within the tolerance, rather than bit-identical floats.
  const allEqual = (arr) => arr.length > 1 && spread(arr) <= tolerance;

  // Cluster indices whose value sits within `tolerance` of the cluster's first
  // member. Anchoring on the first member (not the previous one) stops a long
  // chain of just-under-tolerance steps from drifting into one wide cluster.
  const groupByValue = (indices, valueFn) => {
    const sorted = [...indices].sort((a, b) => valueFn(a) - valueFn(b));
    const groups = [];
    let current = [];
    let anchor = 0;
    for (const i of sorted) {
      const value = valueFn(i);
      if (current.length === 0) {
        anchor = value;
        current.push(i);
      } else if (Math.abs(value - anchor) <= tolerance) {
        current.push(i);
      } else {
        groups.push(current);
        anchor = value;
        current = [i];
      }
    }
    if (current.length > 0) groups.push(current);
    return groups;
  };

  const edgeLabel = (edge) => (edge.includes("center") ? edge : `${edge}-aligned`);

  const Y_EDGES = ["top", "bottom", "center-y"];
  const X_EDGES = ["left", "right", "center-x"];
  const idx = rects.map((_, i) => i);

  // --- Element descriptor ---
  const buildSelector = (el) => {
    if (el.id) return `#${el.id}`;
    const role = el.getAttribute("role");
    const tag = el.tagName.toLowerCase();
    const cls =
      el.className && typeof el.className === "string"
        ? el.className
            .split(" ")
            .filter(Boolean)
            .map((c) => `.${c}`)
            .join("")
        : "";
    return role ? `${tag}[role="${role}"]${cls}` : `${tag}${cls}`;
  };

  const describeElement = (i) => ({
    selector: buildSelector(elements[i]),
    width: Math.round(rects[i].width * 10) / 10,
    height: Math.round(rects[i].height * 10) / 10,
    text: (elements[i].textContent || "").trim().substring(0, 50),
  });

  // --- Gap calculation ---
  // Every gap list reports the same way: the raw floats decide uniformity, so
  // a 0.4px difference between two gaps doesn't read as two different gaps,
  // while the reported values stay rounded to whole pixels.
  const describeGaps = (vals) => {
    if (vals.length === 0) return { uniform: true, values: [] };
    const uniform = spread(vals) <= tolerance;
    const result = { uniform, values: vals.map((v) => `${Math.round(v)}px`) };
    if (uniform) result.value = `${Math.round(vals[0])}px`;
    return result;
  };

  const gapBetween = (prevIdx, currIdx, axis) => {
    const prev = rects[prevIdx];
    const curr = rects[currIdx];
    return axis === "x" ? curr.left - prev.right : curr.top - prev.bottom;
  };

  const calcGaps = (sortedIndices, axis) => {
    if (sortedIndices.length < 2) return { uniform: true, values: [] };
    const vals = [];
    for (let i = 1; i < sortedIndices.length; i++) {
      vals.push(gapBetween(sortedIndices[i - 1], sortedIndices[i], axis));
    }
    return describeGaps(vals);
  };

  const aggregateGaps = (groups, axis) => {
    const all = [];
    for (const g of groups) {
      for (let i = 1; i < g.length; i++) {
        all.push(gapBetween(g[i - 1], g[i], axis));
      }
    }
    return describeGaps(all);
  };

  const calcLineGaps = (groups, axis) => {
    if (groups.length < 2) return { uniform: true, values: [] };
    const vals = [];
    for (let i = 1; i < groups.length; i++) {
      if (axis === "y") {
        const prevBottom = Math.max(...groups[i - 1].map((j) => rects[j].bottom));
        const currTop = Math.min(...groups[i].map((j) => rects[j].top));
        vals.push(currTop - prevBottom);
      } else {
        const prevRight = Math.max(...groups[i - 1].map((j) => rects[j].right));
        const currLeft = Math.min(...groups[i].map((j) => rects[j].left));
        vals.push(currLeft - prevRight);
      }
    }
    return describeGaps(vals);
  };

  // --- Collect alignment labels ---
  const collectAlignments = (indices, yEdges, xEdges) => {
    const labels = [];
    for (const edge of yEdges) {
      if (allEqual(indices.map((i) => yOf(rects[i], edge)))) labels.push(edgeLabel(edge));
    }
    for (const edge of xEdges) {
      if (allEqual(indices.map((i) => xOf(rects[i], edge)))) labels.push(edgeLabel(edge));
    }
    if (allEqual(indices.map((i) => rects[i].width))) labels.push("equal-width");
    if (allEqual(indices.map((i) => rects[i].height))) labels.push("equal-height");
    return labels;
  };

  // ============================================================
  // Single element
  // ============================================================

  if (elements.length === 1) {
    return {
      count: 1,
      tolerance,
      behavior: "single",
      alignment: [],
      lines: [{ elements: [describeElement(0)], gaps: { uniform: true, values: [] } }],
      gaps: { uniform: true, values: [] },
      elements: [describeElement(0)],
    };
  }

  // ============================================================
  // Behaviour checkers
  // ============================================================

  // --- Row: all elements share same Y coordinate ---
  function tryRow() {
    const yAlignments = [];
    for (const edge of Y_EDGES) {
      if (allEqual(idx.map((i) => yOf(rects[i], edge)))) yAlignments.push(edgeLabel(edge));
    }
    if (yAlignments.length === 0) return null;

    const sorted = [...idx].sort((a, b) => rects[a].left - rects[b].left);
    const gaps = calcGaps(sorted, "x");

    const alignment = [...yAlignments];
    if (allEqual(idx.map((i) => rects[i].width))) alignment.push("equal-width");
    if (allEqual(idx.map((i) => rects[i].height))) alignment.push("equal-height");

    return {
      behavior: "row",
      alignment,
      lines: [{ elements: sorted.map(describeElement), gaps }],
      gaps,
    };
  }

  // --- Column: all elements share same X coordinate ---
  function tryColumn() {
    const xAlignments = [];
    for (const edge of X_EDGES) {
      if (allEqual(idx.map((i) => xOf(rects[i], edge)))) xAlignments.push(edgeLabel(edge));
    }
    if (xAlignments.length === 0) return null;

    const sorted = [...idx].sort((a, b) => rects[a].top - rects[b].top);
    const gaps = calcGaps(sorted, "y");

    const alignment = [...xAlignments];
    if (allEqual(idx.map((i) => rects[i].width))) alignment.push("equal-width");
    if (allEqual(idx.map((i) => rects[i].height))) alignment.push("equal-height");

    return {
      behavior: "column",
      alignment,
      lines: [{ elements: sorted.map(describeElement), gaps }],
      gaps,
    };
  }

  // --- Line: elements wrap into horizontal rows within container width ---
  function tryLine() {
    if (!containerRect) return null;

    for (const edge of Y_EDGES) {
      const rows = groupByValue(idx, (i) => yOf(rects[i], edge));
      if (rows.length < 2) continue;

      // Sort rows top-to-bottom, elements within each row left-to-right
      rows.sort((a, b) => rects[a[0]].top - rects[b[0]].top);
      for (const row of rows) row.sort((a, b) => rects[a].left - rects[b].left);

      // Find reference gap from first multi-element row
      let refGap = 0;
      for (const row of rows) {
        if (row.length > 1) {
          refGap = rects[row[1]].left - rects[row[0]].right;
          break;
        }
      }

      // Validate each row
      let valid = true;
      for (let r = 0; r < rows.length; r++) {
        const row = rows[r];
        const rowWidth = rects[row[row.length - 1]].right - rects[row[0]].left;

        // Row must fit inside container
        if (rowWidth > containerRect.width + tolerance) {
          valid = false;
          break;
        }

        // Single-element row (not last): wrapping must be justified. Require
        // the next element to fit with room to spare before calling the wrap
        // unjustified — a borderline fit is exactly what wrapping looks like.
        if (row.length === 1 && r < rows.length - 1) {
          const nextFirst = rects[rows[r + 1][0]];
          if (rects[row[0]].width + refGap + nextFirst.width <= containerRect.width - tolerance) {
            valid = false;
            break;
          }
        }
      }
      if (!valid) continue;

      const alignment = [edgeLabel(edge)];
      if (allEqual(idx.map((i) => rects[i].width))) alignment.push("equal-width");

      return {
        behavior: "line",
        alignment,
        lines: rows.map((row) => ({
          elements: row.map(describeElement),
          gaps: calcGaps(row, "x"),
        })),
        gaps: aggregateGaps(rows, "x"),
        lineGaps: calcLineGaps(rows, "y"),
      };
    }
    return null;
  }

  // --- V-line: elements wrap into vertical columns within container height ---
  function tryVLine() {
    if (!containerRect) return null;

    for (const edge of X_EDGES) {
      const cols = groupByValue(idx, (i) => xOf(rects[i], edge));
      if (cols.length < 2) continue;

      // Sort columns left-to-right, elements within each column top-to-bottom
      cols.sort((a, b) => rects[a[0]].left - rects[b[0]].left);
      for (const col of cols) col.sort((a, b) => rects[a].top - rects[b].top);

      // Find reference gap from first multi-element column
      let refGap = 0;
      for (const col of cols) {
        if (col.length > 1) {
          refGap = rects[col[1]].top - rects[col[0]].bottom;
          break;
        }
      }

      // Validate each column
      let valid = true;
      for (let c = 0; c < cols.length; c++) {
        const col = cols[c];
        const colHeight = rects[col[col.length - 1]].bottom - rects[col[0]].top;

        if (colHeight > containerRect.height + tolerance) {
          valid = false;
          break;
        }

        // Single-element column (not last): wrapping must be justified. Same
        // reasoning as tryLine — a borderline fit is what wrapping looks like.
        if (col.length === 1 && c < cols.length - 1) {
          const nextFirst = rects[cols[c + 1][0]];
          if (rects[col[0]].height + refGap + nextFirst.height <= containerRect.height - tolerance) {
            valid = false;
            break;
          }
        }
      }
      if (!valid) continue;

      const alignment = [edgeLabel(edge)];
      if (allEqual(idx.map((i) => rects[i].height))) alignment.push("equal-height");

      return {
        behavior: "v-line",
        alignment,
        lines: cols.map((col) => ({
          elements: col.map(describeElement),
          gaps: calcGaps(col, "y"),
        })),
        gaps: aggregateGaps(cols, "y"),
        lineGaps: calcLineGaps(cols, "x"),
      };
    }
    return null;
  }

  // --- Grid: multiple rows with non-intersecting Y ranges ---
  function tryGrid() {
    for (const edge of Y_EDGES) {
      const rows = groupByValue(idx, (i) => yOf(rects[i], edge));
      if (rows.length < 2) continue;

      rows.sort((a, b) => rects[a[0]].top - rects[b[0]].top);

      // Rows must not intersect vertically. Touching rows (a 0.5px overlap
      // from rounding) still count as separate rows.
      let valid = true;
      for (let i = 1; i < rows.length; i++) {
        const prevBottom = Math.max(...rows[i - 1].map((j) => rects[j].bottom));
        const currTop = Math.min(...rows[i].map((j) => rects[j].top));
        if (currTop < prevBottom - tolerance) {
          valid = false;
          break;
        }
      }
      if (!valid) continue;

      for (const row of rows) row.sort((a, b) => rects[a].left - rects[b].left);

      const alignment = [edgeLabel(edge)];

      return {
        behavior: "grid",
        alignment,
        lines: rows.map((row) => ({
          elements: row.map(describeElement),
          gaps: calcGaps(row, "x"),
          alignment: collectAlignments(row, Y_EDGES, []),
        })),
        gaps: aggregateGaps(rows, "x"),
        lineGaps: calcLineGaps(rows, "y"),
      };
    }
    return null;
  }

  // ============================================================
  // Run detection: most specific first
  // ============================================================

  const result = tryRow() || tryColumn() || tryLine() || tryVLine() || tryGrid();

  if (result) {
    result.count = elements.length;
    result.tolerance = tolerance;
    result.elements = idx.map(describeElement);
    return result;
  }

  // No layout matched. `tolerance` is reported so that a genuinely odd layout
  // can be told apart from one that just needs more slack than was allowed.
  return {
    count: elements.length,
    tolerance,
    behavior: "unknown",
    alignment: [],
    lines: [],
    gaps: { uniform: false, values: [] },
    elements: idx.map(describeElement),
  };
}
