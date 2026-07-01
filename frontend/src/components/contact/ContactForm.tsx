/** @jsxImportSource preact */
import type { JSX } from "preact";
import { useEffect, useRef, useState } from "preact/hooks";
import { api, ApiError } from "../../lib/api";
import {
  contactLabels,
  resolveLabel,
  type ContactErrorLabels,
} from "./i18n";
import { FormField, type FormFieldProps } from "./FormField";
import { Honeypot } from "./Honeypot";

/**
 * Contact form Preact island (per `contact-form` REQ-contact-form-01,
 * -02, -03, -04, -06).
 *
 * Mounted from `pages/contact.astro` with `client:load` so the form
 * hydrates immediately on the public `/contact` page. The form
 * owns its state locally (no global state, no router, no query
 * layer — it's a single-screen feature). The submit handler calls
 * `api.contacts.submit(...)` from `lib/api.ts`; envelope errors
 * surface as `ApiError` and are mapped to the localized banner
 * shown at the top of the form (per `contact-form` REQ-06).
 *
 * Visual identity: "data terminal" (per the MVP spec). Each field
 * label is prefixed with a `> ` prompt; the submit button is a
 * monospaced `[ Enviar mensaje ]` block with an amber focus ring;
 * success / error / rate-limited states are styled as terminal
 * log lines (`[OK]`, `[ERROR]`, `[429]`) with a monospaced prefix
 * so the feedback reads like a CLI log. The form sits on the
 * existing `bg-bg-surface` slate panel with `border-border` — no
 * shadcn-style card, no rounded-2xl, no shadow-xl.
 *
 * The honeypot is rendered before the visible fields and is
 * positioned off-screen (see `Honeypot.tsx`). The submit button
 * is disabled while the request is in flight; the request also
 * sends `keepalive: true` on the underlying `fetch` via the
 * shared `request()` helper so the submission survives an
 * accidental tab close (per the design's no-data-loss stance).
 */

/** Per-field validation state, keyed by field name. */
type FieldErrors = {
  name: FormFieldProps["errorKey"];
  email: FormFieldProps["errorKey"];
  subject: FormFieldProps["errorKey"];
  message: FormFieldProps["errorKey"];
};

type FormStatus = "idle" | "submitting" | "success" | "error" | "rate_limited";

const EMPTY_ERRORS: FieldErrors = {
  name: null,
  email: null,
  subject: null,
  message: null,
};

// Email regex: a pragmatic, RFC-5322-ish check. We don't try to
// match the spec fully; the backend's Pydantic `EmailStr` is the
// authoritative validator. This regex is the same one browsers
// effectively use for the `type="email"` constraint.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const NAME_MAX = 100;
const SUBJECT_MAX = 200;
const MESSAGE_MIN = 10;
const MESSAGE_MAX = 5000;

/** Per-field validation (exported for unit tests; the form's
 *  behavior contract is "validate returns exactly these errors
 *  for exactly these inputs"). Pure function, no side effects. */
export function validate(
  values: {
    name: string;
    email: string;
    subject: string;
    message: string;
  },
): FieldErrors {
  const errors: FieldErrors = { ...EMPTY_ERRORS };

  const name = values.name.trim();
  if (!name) {
    errors.name = "required";
  } else if (name.length > NAME_MAX) {
    errors.name = "nameTooLong";
  }

  const email = values.email.trim();
  if (!email) {
    errors.email = "required";
  } else if (!EMAIL_RE.test(email)) {
    errors.email = "emailInvalid";
  }

  if (values.subject.length > SUBJECT_MAX) {
    errors.subject = "subjectTooLong";
  }

  const message = values.message;
  // The backend requires at least 10 chars on the message. We
  // also reject if the user has typed nothing (the field is
  // required; show the same "required" error as for any other
  // empty field rather than a confusing length error).
  if (!message.trim()) {
    errors.message = "required";
  } else if (message.length < MESSAGE_MIN) {
    errors.message = "messageTooShort";
  } else if (message.length > MESSAGE_MAX) {
    errors.message = "messageTooLong";
  }

  return errors;
}

/** All-clear check for the validation result. Exported for
 *  unit tests; the form calls it before allowing the submission
 *  to proceed to the network. */
export function isClean(errors: FieldErrors): boolean {
  return (
    errors.name === null &&
    errors.email === null &&
    errors.subject === null &&
    errors.message === null
  );
}

export interface ContactFormProps {
  /** Initial language. The form re-reads `<html data-lang>` on
   *  every render via the `useLang` hook below, so changing the
   *  active language on the page (via LanguageSelector) updates
   *  the form labels live without a remount. */
  initialLang?: "es" | "en";
}

export function ContactForm(
  props: ContactFormProps = {},
): JSX.Element {
  const initialLang: "es" | "en" = props.initialLang ?? "es";

  // ----- form state ------------------------------------------------------
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [honeypot, setHoneypot] = useState("");

  const [errors, setErrors] = useState<FieldErrors>(EMPTY_ERRORS);
  const [status, setStatus] = useState<FormStatus>("idle");
  const [bannerError, setBannerError] = useState<string | null>(null);
  const [lang, setLang] = useState<"es" | "en">(initialLang);

  // The first invalid field is stored so we can move focus to it
  // after a failed submit (per `contact-form` REQ-02 "Empty
  // Required Field Shows Inline Error" — the focus must move to
  // the first invalid field). The refs are populated in render
  // and read in the submit handler.
  const nameRef = useRef<HTMLInputElement | null>(null);
  const emailRef = useRef<HTMLInputElement | null>(null);
  const subjectRef = useRef<HTMLInputElement | null>(null);
  const messageRef = useRef<HTMLTextAreaElement | null>(null);

  // ----- language sync ---------------------------------------------------
  // Read `<html data-lang>` on mount and whenever the language
  // selector mutates the attribute (the selector updates
  // `data-lang` directly via `src/scripts/i18n.ts`). We observe
  // the attribute with a `MutationObserver` so the form labels
  // re-resolve in place without a remount.
  useEffect(() => {
    const update = () => {
      const cur = document.documentElement.getAttribute("data-lang");
      if (cur === "es" || cur === "en") setLang(cur);
    };
    update();
    const obs = new MutationObserver(update);
    obs.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-lang"],
    });
    return () => obs.disconnect();
  }, []);

  // ----- submit handler --------------------------------------------------
  const onSubmit = async (e: JSX.TargetedEvent<HTMLFormElement>) => {
    e.preventDefault();

    const values = { name, email, subject, message };
    const validation = validate(values);
    setErrors(validation);

    if (!isClean(validation)) {
      // Move focus to the first invalid field (per
      // `contact-form` REQ-02). The order matches the visual
      // order: name -> email -> subject -> message.
      setStatus("error");
      setBannerError(null);
      // Defer to next tick so the refs are populated by the
      // re-render triggered by `setErrors`.
      requestAnimationFrame(() => {
        if (validation.name) nameRef.current?.focus();
        else if (validation.email) emailRef.current?.focus();
        else if (validation.subject) subjectRef.current?.focus();
        else if (validation.message) messageRef.current?.focus();
      });
      return;
    }

    setStatus("submitting");
    setBannerError(null);

    try {
      await api.contacts.submit({
        name: name.trim(),
        email: email.trim(),
        subject: subject.trim() || undefined,
        message: message.trim(),
        // `website` is the honeypot. If a bot filled it, the
        // backend will return 400 `bad_request`; we don't
        // differentiate here because the user experience is
        // identical (show the generic error banner).
        website: honeypot,
      });
      setStatus("success");
    } catch (err) {
      // Log every failure with the backend's request id (if any)
      // so a user-reported issue can be correlated with a server
      // log line. This runs BEFORE the state mapping so the
      // console always has the full error context, even for the
      // generic "other error" branch.
      if (err instanceof ApiError) {
        // eslint-disable-next-line no-console
        console.error("[ContactForm] submit failed", {
          code: err.code,
          status: err.status,
          requestId: err.requestId,
        });
        if (err.status === 429 || err.code === "rate_limited") {
          setStatus("rate_limited");
          setBannerError(resolveLabel(contactLabels.state.rateLimited, lang));
        } else if (err.status === 0 || err.code === "network_error") {
          // After commit 3, the api layer reliably throws
          // `ApiError("network_error", ..., 0, requestId)` for
          // timeouts and network failures, so the previously dead
          // `state.networkError` branch is now reachable.
          setStatus("error");
          setBannerError(
            resolveLabel(contactLabels.state.networkError, lang),
          );
        } else {
          setStatus("error");
          setBannerError(resolveLabel(contactLabels.state.error, lang));
        }
      } else {
        // Non-`ApiError` throw (e.g. a coding bug in the api
        // layer). Log it but still surface the generic banner.
        // eslint-disable-next-line no-console
        console.error("[ContactForm] submit failed (unexpected)", err);
        setStatus("error");
        setBannerError(resolveLabel(contactLabels.state.error, lang));
      }
    }
  };

  // ----- success state replaces the form --------------------------------
  if (status === "success") {
    return (
      <div
        role="status"
        aria-live="polite"
        class="grid gap-4 rounded-md border border-border bg-bg-surface p-6 font-mono text-sm"
      >
        <p class="text-xs uppercase tracking-widest text-success">
          <span aria-hidden="true">[OK] </span>
          message_sent
        </p>
        <p class="text-base text-ink-primary">
          {resolveLabel(contactLabels.state.success, lang)}
        </p>
      </div>
    );
  }

  // ----- main form -------------------------------------------------------
  const isSubmitting = status === "submitting";
  const bannerKind = status === "rate_limited" ? "warn" : "error";

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      class="grid gap-5"
      aria-label={resolveLabel(contactLabels.page.heading, lang)}
    >
      {bannerError && (
        <div
          id="contact-error"
          role="alert"
          aria-live="assertive"
          class="flex items-start gap-2 rounded-md border border-error bg-error/10 px-3 py-2 font-mono text-sm text-error"
        >
          <span aria-hidden="true" class="shrink-0">
            [ERROR]
          </span>
          <span>{bannerError}</span>
        </div>
      )}

      <Honeypot value={honeypot} onInput={setHoneypot} />

      <div class="grid gap-5 sm:grid-cols-2">
        <FormField
          ref={nameRef}
          name="name"
          label={contactLabels.fields.name}
          lang={lang}
          errorLabels={contactLabels.errors}
          value={name}
          onInput={setName}
          required
          errorKey={errors.name}
          maxLength={NAME_MAX}
          autoFocus
        />
        <FormField
          ref={emailRef}
          name="email"
          label={contactLabels.fields.email}
          lang={lang}
          errorLabels={contactLabels.errors}
          value={email}
          onInput={setEmail}
          required
          type="email"
          errorKey={errors.email}
          maxLength={254}
        />
      </div>
      <FormField
        ref={subjectRef}
        name="subject"
        label={contactLabels.fields.subject}
        lang={lang}
        errorLabels={contactLabels.errors}
        value={subject}
        onInput={setSubject}
        errorKey={errors.subject}
        maxLength={SUBJECT_MAX}
      />
      <FormField
        ref={messageRef}
        name="message"
        label={contactLabels.fields.message}
        lang={lang}
        errorLabels={contactLabels.errors}
        value={message}
        onInput={setMessage}
        required
        multiline
        errorKey={errors.message}
        maxLength={MESSAGE_MAX}
      />

      <div class="flex flex-wrap items-center gap-3 pt-2">
        <button
          type="submit"
          disabled={isSubmitting}
          class={[
            "inline-flex items-center gap-2 rounded-md border px-4 py-2",
            "font-mono text-sm font-semibold",
            "transition-colors",
            "focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-bg-base",
            isSubmitting
              ? "cursor-not-allowed border-border bg-bg-elevated text-ink-tertiary"
              : "border-accent bg-accent text-bg-base hover:bg-accent-hover",
          ].join(" ")}
          aria-busy={isSubmitting}
        >
          <span aria-hidden="true">▸</span>
          {isSubmitting
            ? lang === "en"
              ? "Sending…"
              : "Enviando…"
            : resolveLabel(contactLabels.fields.submit, lang)}
        </button>
        <p
          class="font-mono text-xs text-ink-tertiary"
          aria-hidden={bannerKind === "error" ? "false" : "true"}
        >
          <span aria-hidden="true">$ </span>
          {lang === "en"
            ? "POST /api/v1/contacts"
            : "POST /api/v1/contacts"}
        </p>
      </div>
    </form>
  );
}
