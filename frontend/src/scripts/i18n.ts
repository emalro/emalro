/**
 * i18n client-side swap.
 *
 * Every localizable element in the DOM carries a `data-i18n` attribute
 * whose value is a JSON-encoded LocalizedStr ({ es, en }). On load and
 * whenever the language changes, this script walks the [data-i18n]
 * elements and sets either textContent or innerHTML to the right key
 * for the current data-lang attribute on <html>. Empty `en` falls back
 * to `es` silently (REQ-i18n-01).
 *
 * For elements that contain Markdown (carrying the optional
 * `data-i18n-html` attribute), the script runs `renderMarkdown` on the
 * resolved string and assigns the result to `innerHTML`. This is
 * required for the non-blog surfaces (personal.summary, experience
 * descriptions, etc.) which were reformatted as Markdown in the
 * content polish PR — see `src/lib/markdown.ts` for the renderer.
 *
 * The language selector (LanguageSelector.astro) updates data-lang on
 * click; this script re-runs the swap automatically because it listens
 * to the same buttons.
 */

import { renderMarkdown } from "../lib/markdown";
import type { LocalizedStr } from "../types/content";

const LANG_KEY = "lang";

function currentLang(): "es" | "en" {
  return (document.documentElement.getAttribute("data-lang") as
    | "es"
    | "en") || "es";
}

function setLang(lang: "es" | "en") {
  document.documentElement.setAttribute("data-lang", lang);
  document.documentElement.setAttribute("lang", lang);
  try {
    localStorage.setItem(LANG_KEY, lang);
  } catch {
    /* ignore */
  }
  // Reflect active state on the selector buttons
  document
    .querySelectorAll<HTMLButtonElement>("[data-lang-select]")
    .forEach((btn) => {
      const active = btn.dataset.langSelect === lang;
      btn.setAttribute("aria-pressed", active ? "true" : "false");
      btn.dataset.active = active ? "true" : "false";
    });
  applyAll();
}

function resolve(str: LocalizedStr, lang: "es" | "en"): string {
  const v = str[lang];
  return v && v.length > 0 ? v : str.es;
}

function applyAll() {
  const lang = currentLang();
  document.querySelectorAll<HTMLElement>("[data-i18n]").forEach((el) => {
    const raw = el.getAttribute("data-i18n");
    if (!raw) return;
    try {
      const parsed = JSON.parse(raw) as LocalizedStr;
      const text = resolve(parsed, lang);
      // `data-i18n-html` marks elements whose resolved value is
      // Markdown and must be rendered as HTML. The renderer is the
      // same one used by the Astro components at build time so the
      // server-rendered DOM and the client swap stay in sync.
      if (el.hasAttribute("data-i18n-html")) {
        el.innerHTML = renderMarkdown(text);
      } else {
        el.textContent = text;
      }
    } catch {
      /* malformed data-i18n — leave as-is, build-time validator should have caught it */
    }
  });
}

function init() {
  document
    .querySelectorAll<HTMLButtonElement>("[data-lang-select]")
    .forEach((btn) => {
      btn.addEventListener("click", () => {
        const next = btn.dataset.langSelect as "es" | "en" | undefined;
        if (next) setLang(next);
      });
    });
  applyAll();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
