/** @jsxImportSource preact */
import type { JSX } from "preact";
import { useId } from "preact/hooks";
import { resolveLabel, type ContactErrorLabels } from "./i18n";
import type { LocalizedStr } from "../../types/content";

/**
 * Accessible form field with inline error message (per
 * `contact-form` REQ-contact-form-01 + -02).
 *
 * The label is rendered ABOVE the input (mobile-first, data-terminal
 * aesthetic). On validation failure the input gets `aria-invalid="true"`
 * and a visually-distinct ring; the inline error text below uses
 * `aria-live="polite"` so screen readers announce it without
 * interrupting the user.
 *
 * The visual style is data-terminal: each field's label is prefixed
 * with a `> ` prompt character (matching the data-terminal aesthetic
 * described in the MVP spec). The input itself is a single-line
 * monospaced field, slate-on-slate, with an amber focus ring.
 *
 * Props are stable references on the parent (`ContactForm.tsx`),
 * so this component renders cheaply without memoization.
 */
export interface FormFieldProps {
  /** Field name (used as the `name` attribute and as the key in the
   *  parent's `errors` map). */
  name: "name" | "email" | "subject" | "message";
  /** Localized label (e.g. { es: "Nombre", en: "Name" }). */
  label: LocalizedStr;
  /** Active language — drives label resolution. */
  lang: "es" | "en";
  /** The localized inline error label set (used to render the
   *  per-field error string). The actual error key (e.g. `required`,
   *  `emailInvalid`) is selected by the parent. */
  errorLabels: ContactErrorLabels;
  /** Current value. */
  value: string;
  /** Change handler (Preact passes the event object). */
  onInput: (value: string) => void;
  /** When set, the field is marked required (label gets `*` suffix
   *  and HTML `required` attribute is added). */
  required?: boolean;
  /** Current validation error key (or `null` if valid). When set,
   *  the field is marked invalid and the localized error message
   *  is rendered below. */
  errorKey:
    | null
    | "required"
    | "emailInvalid"
    | "nameTooLong"
    | "messageTooShort"
    | "messageTooLong"
    | "subjectTooLong";
  /** When true, the field is rendered as a `<textarea>` (used for
   *  the `message` field). Otherwise a single-line `<input>`. */
  multiline?: boolean;
  /** `type` attribute for the `<input>` element (default `text`).
   *  Ignored when `multiline` is true. */
  type?: "text" | "email";
  /** Max length (matches the backend Pydantic constraint). */
  maxLength?: number;
  /** Optional placeholder, already i18n-resolved. */
  placeholder?: string;
  /** Whether to auto-focus this field on mount. The parent should
   *  set this on the first invalid field after a failed submit. */
  autoFocus?: boolean;
}

export function FormField(props: FormFieldProps): JSX.Element {
  const {
    name,
    label,
    lang,
    errorLabels,
    value,
    onInput,
    required = false,
    errorKey,
    multiline = false,
    type = "text",
    maxLength,
    placeholder,
    autoFocus = false,
  } = props;

  // `useId` is stable across renders; pairing label + error message
  // to the input via `htmlFor` / `aria-describedby` is the standard
  // accessible-form pattern. The `useId` is preact-hooks-only and
  // SSR-safe (Astro renders the page statically and Preact
  // hydrates on the client).
  const inputId = useId();
  const errorId = `${inputId}-error`;

  const labelText = resolveLabel(label, lang);
  const requiredMark = required ? " *" : "";
  const errorText = errorKey ? resolveLabel(errorLabels[errorKey], lang) : null;

  const handleInput = (
    e: JSX.TargetedEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    onInput((e.currentTarget as HTMLInputElement | HTMLTextAreaElement).value);
  };

  // Common Tailwind classes shared between input/textarea.
  const fieldClasses = [
    "block w-full rounded-md border bg-bg-surface px-3 py-2 font-mono text-sm",
    "text-ink-primary placeholder:text-ink-tertiary",
    "transition-colors",
    "focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base",
    errorKey
      ? "border-error focus:border-error focus:ring-error"
      : "border-border focus:border-accent focus:ring-accent",
  ].join(" ");

  // Label row: `> ` prompt + label text + required marker.
  const labelClasses = [
    "font-mono text-xs uppercase tracking-widest",
    errorKey ? "text-error" : "text-accent",
  ].join(" ");

  // Inline error message: a small `!` prefix to keep the terminal
  // voice consistent with the rest of the form.
  const errorClasses = "font-mono text-xs text-error";

  return (
    <div class="grid gap-1.5">
      <label htmlFor={inputId} class={labelClasses}>
        <span aria-hidden="true">&gt; </span>
        {labelText}
        {requiredMark && (
          <span class="text-error" aria-hidden="true">
            *
          </span>
        )}
        {required && <span class="sr-only"> (requerido)</span>}
      </label>
      {multiline ? (
        <textarea
          id={inputId}
          name={name}
          value={value}
          onInput={handleInput}
          required={required}
          maxLength={maxLength}
          rows={6}
          aria-invalid={errorKey ? "true" : "false"}
          aria-describedby={errorText ? errorId : undefined}
          autoFocus={autoFocus}
          placeholder={placeholder}
          class={fieldClasses}
        />
      ) : (
        <input
          id={inputId}
          name={name}
          type={type}
          value={value}
          onInput={handleInput}
          required={required}
          maxLength={maxLength}
          aria-invalid={errorKey ? "true" : "false"}
          aria-describedby={errorText ? errorId : undefined}
          autoFocus={autoFocus}
          placeholder={placeholder}
          class={fieldClasses}
          autoComplete={
            type === "email"
              ? "email"
              : name === "name"
                ? "name"
                : "off"
          }
        />
      )}
      {errorText && (
        <p id={errorId} role="alert" aria-live="polite" class={errorClasses}>
          <span aria-hidden="true">! </span>
          {errorText}
        </p>
      )}
    </div>
  );
}
