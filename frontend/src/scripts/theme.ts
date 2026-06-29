/**
 * Theme toggle handler.
 *
 * Bound to the theme toggle button rendered by ThemeToggle.astro.
 * Reads the current data-theme from <html>, swaps it, persists to
 * localStorage, and updates the button's icon + aria-label.
 */

const THEME_KEY = "theme";

function current(): "dark" | "light" {
  return (document.documentElement.getAttribute("data-theme") as
    | "dark"
    | "light") || "dark";
}

function paint(theme: "dark" | "light") {
  const root = document.documentElement;
  root.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* ignore */
  }
  const btn = document.querySelector<HTMLButtonElement>("[data-theme-toggle]");
  if (!btn) return;
  btn.setAttribute("aria-pressed", theme === "dark" ? "false" : "true");
  btn.setAttribute(
    "aria-label",
    theme === "dark" ? "Switch to light theme" : "Switch to dark theme",
  );
  btn.dataset.icon = theme === "dark" ? "sun" : "moon";
}

function init() {
  const btn = document.querySelector<HTMLButtonElement>("[data-theme-toggle]");
  if (!btn) return;
  paint(current());
  btn.addEventListener("click", () => {
    paint(current() === "dark" ? "light" : "dark");
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
