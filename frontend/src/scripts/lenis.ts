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
 * When `prefers-reduced-motion: reduce` is set, this module is a
 * no-op: native browser scroll is used, and global.css overrides
 * `scroll-behavior` to auto so jumps are instant. The CSS gate also
 * flattens any Lenis transition that may have been scheduled.
 */

import Lenis from "lenis";

const NAVBAR_OFFSET_PX = -64; // --navbar-h: 4rem in global.css

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function targetFor(href: string): HTMLElement | null {
  // Accept both "#hero" (same-page anchor) and "/#hero" (cross-page
  // with hash). Extract the hash part and query by it.
  const hashIdx = href.indexOf("#");
  if (hashIdx === -1 || href.length < hashIdx + 2) return null;
  return document.querySelector<HTMLElement>(href.slice(hashIdx));
}

function init() {
  // Native scroll is enough when the user has opted out of motion.
  if (reducedMotion()) return;

  const lenis = new Lenis({
    duration: 1.1,
    smoothWheel: true,
  });

  function raf(time: number) {
    lenis.raf(time);
    requestAnimationFrame(raf);
  }
  requestAnimationFrame(raf);

  // Bind anchor clicks that target an in-page section.
  // The selector catches both "#hero" and "/#hero" forms so the
  // navbar works from any route (homepage and /contact, /blog/*).
  document.querySelectorAll<HTMLAnchorElement>("a[href*='#']").forEach((a) => {
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
