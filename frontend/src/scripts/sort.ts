/**
 * Generic client-side sort for chronological sections.
 *
 * Each section's list root carries `data-sort-root`; its children
 * carry `data-sort-value` (an ISO YYYY-MM date, parsed as a number
 * so 202401 > 202312). Missing/empty `data-sort-value` is treated as
 * +Infinity so current jobs (end_date: null) always sort first in
 * descending order.
 *
 * SortControl.astro writes `data-sort-dir` to the root on each click.
 */

type Dir = "desc" | "asc";

function valueOf(el: HTMLElement): number {
  const raw = el.dataset.sortValue;
  if (!raw || raw === "null") return Number.POSITIVE_INFINITY;
  const n = Number(raw);
  return Number.isFinite(n) ? n : Number.NEGATIVE_INFINITY;
}

function sortRoot(root: HTMLElement): void {
  const dir = (root.dataset.sortDir as Dir) || "desc";
  const items = Array.from(
    root.querySelectorAll<HTMLElement>(":scope > [data-sort-value]"),
  );
  items.sort((a, b) => (dir === "desc" ? valueOf(b) - valueOf(a) : valueOf(a) - valueOf(b)));
  items.forEach((item) => root.appendChild(item));
}

function init(): void {
  document.querySelectorAll<HTMLElement>("[data-sort-root]").forEach(sortRoot);
  document.querySelectorAll<HTMLButtonElement>("[data-sort-control]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const root = document.getElementById(btn.dataset.sortControl ?? "");
      if (!root) return;
      root.dataset.sortDir = btn.dataset.sortDir || "desc";
      sortRoot(root);
      const group = btn.closest("[data-sort-group]");
      if (!group) return;
      group.querySelectorAll<HTMLButtonElement>("[data-sort-control]").forEach((b) => {
        const active = b === btn;
        b.setAttribute("aria-pressed", active ? "true" : "false");
        b.dataset.active = active ? "true" : "false";
      });
    });
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
