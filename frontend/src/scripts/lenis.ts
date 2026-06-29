/**
 * Lenis smooth scroll.
 *
 * Initializes a single Lenis instance and binds it to anchor clicks
 * inside the page. The animation is driven by Lenis; the final
 * position is offset by --navbar-h so the section title lands below
 * the fixed navbar (the same value is also applied to sections via
 * `scroll-margin-top: var(--navbar-h)` in global.css for non-Lenis
 * paths like keyboard nav and direct anchor URLs).
 *
 * TODO(reduced-motion): PR #3 must gate the Lenis init behind a
 * `window.matchMedia('(prefers-reduced-motion: reduce)').matches`
 * check. Users with the preference set will get native scrolling and
 * a static role line.
 */

import Lenis from "lenis";

const NAVBAR_OFFSET_PX = -64; // --navbar-h: 4rem in global.css

function targetFor(href: string): HTMLElement | null {
  if (!href.startsWith("#") || href.length < 2) return null;
  return document.querySelector<HTMLElement>(href);
}

function init() {
  const lenis = new Lenis({
    duration: 1.1,
    smoothWheel: true,
  });

  function raf(time: number) {
    lenis.raf(time);
    requestAnimationFrame(raf);
  }
  requestAnimationFrame(raf);

  // Bind anchor clicks that target an in-page section
  document.querySelectorAll<HTMLAnchorElement>("a[href^='#']").forEach((a) => {
    a.addEventListener("click", (e) => {
      const href = a.getAttribute("href");
      if (!href) return;
      const target = targetFor(href);
      if (!target) return;
      e.preventDefault();
      lenis.scrollTo(target, { offset: NAVBAR_OFFSET_PX });
    });
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
