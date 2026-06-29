/**
 * Pre-paint bootstrap for theme + language.
 *
 * This script MUST run before first paint to avoid the FOUC of
 * the wrong theme/language (REQ-theme-04, REQ-i18n-06). It is
 * bundled by Astro and inlined into the document <head>.
 *
 * The data-theme and data-lang attributes are the source of truth
 * for everything downstream (Tailwind dark variants, i18n resolver,
 * theme toggle, language selector).
 */

const THEME_KEY = "theme";
const LANG_KEY = "lang";
const DEFAULT_THEME: "dark" | "light" = "dark";
const DEFAULT_LANG: "es" | "en" = "es";

type Theme = typeof DEFAULT_THEME;
type Lang = typeof DEFAULT_LANG;

function readStored<T extends string>(
  key: string,
  fallback: T,
  allowed: readonly T[],
): T {
  try {
    const raw = localStorage.getItem(key);
    if (raw && (allowed as readonly string[]).includes(raw)) return raw as T;
  } catch {
    /* localStorage may be blocked (private mode, SSR) */
  }
  return fallback;
}

const root = document.documentElement;
const theme = readStored<Theme>(THEME_KEY, DEFAULT_THEME, [
  "dark",
  "light",
] as const);
const lang = readStored<Lang>(LANG_KEY, DEFAULT_LANG, ["es", "en"] as const);

root.setAttribute("data-theme", theme);
root.setAttribute("data-lang", lang);
root.setAttribute("lang", lang);
