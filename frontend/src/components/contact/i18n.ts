/**
 * Contact form labels (per `contact-form` REQ-contact-form-01 + -06).
 *
 * Every localizable string on the public `/contact` page lives here
 * in the JSONB `LocalizedStr` shape (`{ es, en }`). The Ajv schema
 * at `src/data/schemas/contact.schema.json` self-tests a canonical
 * sample of this shape on every build (per `i18n-shape`
 * REQ-i18n-shape-05); the TS module is the runtime source of truth
 * for the form components.
 *
 * The runtime consumer (`ContactForm.tsx`, `FormField.tsx`) reads the
 * active language from `<html data-lang>` and resolves the
 * `LocalizedStr` against it, falling back to `es` when the active
 * `en` value is empty (matching the project-wide `i18n-shape`
 * REQ-i18n-shape-02 contract).
 *
 * Labels are part of the "data terminal" visual identity (per
 * design Section 14): each field's label is prefixed with a `> `
 * prompt character at render time, so the raw label here stays plain
 * text (the prefix is added by the component, not stored in i18n).
 */

import type { LocalizedStr } from "../../lib/api";

/** Field-level labels: name, email, subject, message, submit. */
export type ContactFieldLabels = {
  name: LocalizedStr;
  email: LocalizedStr;
  subject: LocalizedStr;
  message: LocalizedStr;
  submit: LocalizedStr;
};

/** UI-state labels: success confirmation + the rate-limit / generic error banner. */
export type ContactStateLabels = {
  success: LocalizedStr;
  error: LocalizedStr;
  rateLimited: LocalizedStr;
  networkError: LocalizedStr;
};

/** Inline field-level error messages, keyed by field name. */
export type ContactErrorLabels = {
  required: LocalizedStr;
  emailInvalid: LocalizedStr;
  messageTooShort: LocalizedStr;
  messageTooLong: LocalizedStr;
  subjectTooLong: LocalizedStr;
  nameTooLong: LocalizedStr;
};

export type ContactLabels = {
  /** Page-level: eyebrow + heading + intro paragraph + back link. */
  page: {
    eyebrow: LocalizedStr;
    heading: LocalizedStr;
    intro: LocalizedStr;
    backLink: LocalizedStr;
  };
  /** Field labels rendered next to inputs. */
  fields: ContactFieldLabels;
  /** Inline error messages rendered under each field. */
  errors: ContactErrorLabels;
  /** Top-of-form / success / rate-limit banners. */
  state: ContactStateLabels;
};

/**
 * Canonical label set. The Spanish copy follows the project's
 * existing register (informal second-person plural / voseo-free
 * standard Spanish), and the English copy is concise and direct.
 *
 * The form does NOT need a captcha or external anti-bot (the
 * honeypot is the only bot defense in Fase 2 per the design), so
 * the label set stays compact.
 */
export const contactLabels: ContactLabels = {
  page: {
    eyebrow: { es: "// 05", en: "// 05" },
    heading: { es: "Contacto", en: "Contact" },
    intro: {
      es: "Dejame tu mensaje y te respondo a la brevedad. Los campos con * son obligatorios.",
      en: "Drop me a message and I'll get back to you soon. Fields marked * are required.",
    },
    backLink: { es: "← Volver al inicio", en: "← Back to home" },
  },
  fields: {
    name: { es: "Nombre", en: "Name" },
    email: { es: "Email", en: "Email" },
    subject: { es: "Asunto (opcional)", en: "Subject (optional)" },
    message: { es: "Mensaje", en: "Message" },
    submit: { es: "Enviar mensaje", en: "Send message" },
  },
  errors: {
    required: {
      es: "Este campo es obligatorio.",
      en: "This field is required.",
    },
    emailInvalid: {
      es: "Ingresá un email válido.",
      en: "Please enter a valid email address.",
    },
    messageTooShort: {
      es: "El mensaje debe tener al menos 10 caracteres.",
      en: "The message must be at least 10 characters.",
    },
    messageTooLong: {
      es: "El mensaje no puede superar los 5000 caracteres.",
      en: "The message must be 5000 characters or fewer.",
    },
    subjectTooLong: {
      es: "El asunto no puede superar los 200 caracteres.",
      en: "The subject must be 200 characters or fewer.",
    },
    nameTooLong: {
      es: "El nombre no puede superar los 100 caracteres.",
      en: "The name must be 100 characters or fewer.",
    },
  },
  state: {
    success: {
      es: "¡Gracias! Tu mensaje fue recibido. Te respondo pronto.",
      en: "Thanks! Your message was received. I'll get back to you soon.",
    },
    error: {
      es: "No se pudo enviar el mensaje. Revisá los campos e intentá de nuevo.",
      en: "Couldn't send the message. Please check the fields and try again.",
    },
    rateLimited: {
      es: "Demasiados intentos. Esperá un momento antes de enviar otro mensaje.",
      en: "Too many attempts. Please wait a moment before sending another message.",
    },
    networkError: {
      es: "Sin conexión con el servidor. Verificá tu red e intentá de nuevo.",
      en: "Can't reach the server. Check your connection and try again.",
    },
  },
};

/**
 * Resolve a `LocalizedStr` against the active language, falling back
 * to Spanish when the active value is empty (matches the project
 * i18n contract: `en` may be empty, `es` is never empty).
 */
export function resolveLabel(
  str: LocalizedStr,
  lang: "es" | "en",
): string {
  const v = str[lang];
  return v && v.length > 0 ? v : str.es;
}
