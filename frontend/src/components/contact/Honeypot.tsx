/** @jsxImportSource preact */
import type { JSX } from "preact";
import { useId } from "preact/hooks";

/**
 * Honeypot field (per `contact-form` REQ-contact-form-01).
 *
 * Real users never see or fill this field — it's positioned
 * off-screen with absolute positioning, `tabindex=-1`, and
 * `aria-hidden="true"`. Bots that auto-fill all visible fields
 * will also fill this one; the backend then silently drops the
 * submission with a 400 `honeypot_triggered` error.
 *
 * The on-screen label is intentionally a "do not fill" prompt
 * to be doubly safe: if a screen reader ever reads it, the user
 * is told not to interact. The label is also a `LocalizedStr`
 * (always English; not user-facing) so the JSONB-shape
 * discipline applies to every string the form touches.
 *
 * The component is a no-op render when the field is hidden; it
 * exists solely to keep the parent's form state wiring simple.
 */
export interface HoneypotProps {
  /** Current value. Real users always pass `""`. */
  value: string;
  /** Change handler. Real users never fire it. */
  onInput: (value: string) => void;
}

export function Honeypot(props: HoneypotProps): JSX.Element {
  // The input is positioned far off-screen using a negative
  // `left` and `top`, so screen readers and tab navigation skip
  // it (tabindex=-1 + aria-hidden=true). The wrapper carries
  // `aria-hidden="true"` and a CSS class that does the visual
  // hiding (`sr-only` is not enough — some accessibility tools
  // will still expose `sr-only` elements, so we use a custom
  // off-screen technique). The form field is also explicitly
  // `autocomplete="off"` so password managers don't fill it.
  const id = useId();

  const handleInput = (e: JSX.TargetedEvent<HTMLInputElement>) => {
    props.onInput(e.currentTarget.value);
  };

  return (
    <div
      aria-hidden="true"
      style={{
        position: "absolute",
        left: "-10000px",
        top: "auto",
        width: "1px",
        height: "1px",
        overflow: "hidden",
      }}
    >
      <label htmlFor={id} class="sr-only">
        Do not fill this field
      </label>
      <input
        id={id}
        type="text"
        name="website"
        value={props.value}
        onInput={handleInput}
        tabIndex={-1}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        spellcheck={false}
        data-testid="honeypot"
      />
    </div>
  );
}
