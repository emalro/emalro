/**
 * Hero role typing animation.
 *
 * Renders the localized role string character-by-character, pauses,
 * backspaces, then types the alternate locale. Loops on a single
 * page session. Anchored to the element with `data-typed-role` and
 * a child <span data-typed-cursor>.
 *
 * When `prefers-reduced-motion: reduce` is set, the animation does
 * not start: the role stays as the static ES text Astro rendered
 * and the blinking cursor is removed from the DOM (the global CSS
 * @media rule flattens any remaining CSS animation as a safety net).
 */

const TYPING = 80;
const BACKSPACE = 40;
const PAUSE = 1500;

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function setText(node: Text | null, value: string): void {
  if (node) node.data = value;
}

function start(): void {
  const el = document.querySelector<HTMLElement>("[data-typed-role]");
  if (!el) return;

  // No animation: leave the static ES text in place and drop the cursor.
  if (reducedMotion()) {
    const cursor = el.querySelector("[data-typed-cursor]");
    cursor?.remove();
    return;
  }

  const es = el.dataset.typedRole ?? "";
  const en = el.dataset.typedRoleEn ?? "";
  const text = document.createTextNode(es);
  if (el.firstChild) el.replaceChild(text, el.firstChild);
  else el.insertBefore(text, el.firstChild);
  el.appendChild(el.querySelector("[data-typed-cursor]")!);

  let buffer = es;
  let locale = 0; // 0=es, 1=en
  let i = buffer.length;

  function type(): void {
    if (i >= (locale === 0 ? es.length : en.length)) {
      setTimeout(swap, PAUSE);
      return;
    }
    if (locale === 0) buffer += es[i];
    else buffer += en[i];
    i++;
    setText(text, buffer);
    setTimeout(type, TYPING);
  }

  function backspace(): void {
    if (buffer.length === 0) {
      locale = locale === 0 ? 1 : 0;
      i = 0;
      setTimeout(type, TYPING);
      return;
    }
    buffer = buffer.slice(0, -1);
    setText(text, buffer);
    setTimeout(backspace, BACKSPACE);
  }

  function swap(): void {
    backspace();
  }

  setTimeout(backspace, PAUSE);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", start);
} else {
  start();
}
