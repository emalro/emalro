/** @jsxImportSource preact */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/preact";
import { ApiError, api } from "../../lib/api";
import { ContactForm, isClean, validate } from "./ContactForm";

/**
 * Unit tests for the contact form (per `contact-form` REQ-01..06
 * and the 4R review follow-ups R3-C1, R4-C2, R4-C4, R4-C7).
 *
 * Two layers of coverage:
 * - Pure validation: `validate()` and `isClean()` (no DOM).
 * - Form behavior: catch-branch mapping for the three error
 *   families the frontend can see (network, rate-limit,
 *   validation/server), the success transition, and the
 *   i18n switch.
 *
 * The api layer is mocked so the tests don't hit the network
 * (and so we can deterministically inject every `ApiError`
 * variant without standing up a server).
 */

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  // Reset the global language back to "es" so a test that
  // switched to "en" does not leak into the next test.
  document.documentElement.setAttribute("data-lang", "es");
});

// ---------------------------------------------------------------------------
// validate() — pure function
// ---------------------------------------------------------------------------

const VALID_VALUES = {
  name: "Alice",
  email: "alice@example.com",
  subject: "Hello",
  message: "This is a valid message body of sufficient length.",
};

describe("validate()", () => {
  it("returns no errors for a fully-valid payload", () => {
    expect(validate(VALID_VALUES)).toEqual({
      name: null,
      email: null,
      subject: null,
      message: null,
    });
  });

  it("flags an empty name as 'required'", () => {
    const e = validate({ ...VALID_VALUES, name: "" });
    expect(e.name).toBe("required");
  });

  it("flags whitespace-only name as 'required' (the form trims first)", () => {
    const e = validate({ ...VALID_VALUES, name: "   " });
    expect(e.name).toBe("required");
  });

  it("flags a name longer than 100 chars as 'nameTooLong'", () => {
    const e = validate({ ...VALID_VALUES, name: "x".repeat(101) });
    expect(e.name).toBe("nameTooLong");
  });

  it("accepts a name exactly at the 100-char boundary", () => {
    const e = validate({ ...VALID_VALUES, name: "x".repeat(100) });
    expect(e.name).toBeNull();
  });

  it("flags an empty email as 'required'", () => {
    const e = validate({ ...VALID_VALUES, email: "" });
    expect(e.email).toBe("required");
  });

  it("flags an invalid email as 'emailInvalid'", () => {
    const e = validate({ ...VALID_VALUES, email: "not-an-email" });
    expect(e.email).toBe("emailInvalid");
  });

  it("accepts a typical valid email", () => {
    const e = validate({ ...VALID_VALUES, email: "user.name+tag@example.co" });
    expect(e.email).toBeNull();
  });

  it("flags a subject longer than 200 chars as 'subjectTooLong'", () => {
    const e = validate({ ...VALID_VALUES, subject: "x".repeat(201) });
    expect(e.subject).toBe("subjectTooLong");
  });

  it("accepts an empty subject (it is optional)", () => {
    const e = validate({ ...VALID_VALUES, subject: "" });
    expect(e.subject).toBeNull();
  });

  it("flags an empty message as 'required'", () => {
    const e = validate({ ...VALID_VALUES, message: "" });
    expect(e.message).toBe("required");
  });

  it("flags a message shorter than 10 chars as 'messageTooShort'", () => {
    const e = validate({ ...VALID_VALUES, message: "too short" });
    expect(e.message).toBe("messageTooShort");
  });

  it("accepts a message exactly at the 10-char boundary", () => {
    const e = validate({ ...VALID_VALUES, message: "x".repeat(10) });
    expect(e.message).toBeNull();
  });

  it("flags a message longer than 5000 chars as 'messageTooLong'", () => {
    const e = validate({ ...VALID_VALUES, message: "x".repeat(5001) });
    expect(e.message).toBe("messageTooLong");
  });

  it("reports ALL invalid fields at once (not just the first)", () => {
    const e = validate({
      name: "",
      email: "bad",
      subject: "x".repeat(201),
      message: "hi",
    });
    expect(e.name).toBe("required");
    expect(e.email).toBe("emailInvalid");
    expect(e.subject).toBe("subjectTooLong");
    expect(e.message).toBe("messageTooShort");
  });
});

describe("isClean()", () => {
  it("returns true when every field error is null", () => {
    expect(
      isClean({ name: null, email: null, subject: null, message: null }),
    ).toBe(true);
  });

  it("returns false when any field has an error", () => {
    expect(
      isClean({
        name: "required",
        email: null,
        subject: null,
        message: null,
      }),
    ).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Form behavior — catch-branch mapping
// ---------------------------------------------------------------------------

function fillValid(getAllByRole: ReturnType<typeof render>["getAllByRole"]) {
  const inputs = getAllByRole("textbox");
  // The visible text fields in DOM order: name, email, subject, message.
  // `getAllByRole("textbox")` also returns <input type="email">.
  fireEvent.input(inputs[0], { target: { value: "Alice" } });
  fireEvent.input(inputs[1], { target: { value: "alice@example.com" } });
  fireEvent.input(inputs[2], { target: { value: "Hello" } });
  fireEvent.input(inputs[3], {
    target: { value: "This is a valid message body of sufficient length." },
  });
}

describe("ContactForm submit catch branches", () => {
  beforeEach(() => {
    // The form reads `<html data-lang>` on mount.
    document.documentElement.setAttribute("data-lang", "es");
  });

  it("sets the network-error banner for ApiError('network_error', 0)", async () => {
    const submit = vi
      .spyOn(api.contacts, "submit")
      .mockRejectedValueOnce(
        new ApiError("network_error", "No connection", 0, "req-123"),
      );

    const { getByRole, findByText, getAllByRole } = render(<ContactForm />);
    fillValid(getAllByRole);

    fireEvent.click(getByRole("button", { name: /enviar mensaje/i }));

    await waitFor(() => {
      expect(submit).toHaveBeenCalledTimes(1);
    });
    // The Spanish "no connection" copy.
    const banner = await findByText(/sin conexi[oó]n/i);
    expect(banner).toBeTruthy();
    // The banner is reachable via the contact-error id.
    const bannerEl = document.getElementById("contact-error");
    expect(bannerEl).toBeTruthy();
    expect(bannerEl?.getAttribute("role")).toBe("alert");
  });

  it("sets the rate-limited banner for ApiError('rate_limited', 429)", async () => {
    vi.spyOn(api.contacts, "submit").mockRejectedValueOnce(
      new ApiError("rate_limited", "Slow down", 429, "req-456"),
    );

    const { getByRole, findByText, getAllByRole } = render(<ContactForm />);
    fillValid(getAllByRole);

    fireEvent.click(getByRole("button", { name: /enviar mensaje/i }));

    const banner = await findByText(/demasiados intentos/i);
    expect(banner).toBeTruthy();
  });

  it("sets the generic error banner for an unexpected 4xx/5xx", async () => {
    vi.spyOn(api.contacts, "submit").mockRejectedValueOnce(
      new ApiError("server_error", "Boom", 500, "req-789"),
    );

    const { getByRole, findByText, getAllByRole } = render(<ContactForm />);
    fillValid(getAllByRole);

    fireEvent.click(getByRole("button", { name: /enviar mensaje/i }));

    const banner = await findByText(
      /no se pudo enviar el mensaje|revis[aá] los campos/i,
    );
    expect(banner).toBeTruthy();
  });

  it("logs the failed submit with the backend request id (R4-C4)", async () => {
    const errSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    vi.spyOn(api.contacts, "submit").mockRejectedValueOnce(
      new ApiError("validation_error", "Bad fields", 422, "req-abc"),
    );

    const { getByRole, getAllByRole } = render(<ContactForm />);
    fillValid(getAllByRole);
    fireEvent.click(getByRole("button", { name: /enviar mensaje/i }));

    await waitFor(() => {
      expect(errSpy).toHaveBeenCalled();
    });
    const call = errSpy.mock.calls.find(
      (c) => Array.isArray(c) && c[0] === "[ContactForm] submit failed",
    );
    expect(call).toBeDefined();
    const payload = call?.[1] as { code: string; status: number; requestId: string };
    expect(payload.code).toBe("validation_error");
    expect(payload.status).toBe(422);
    expect(payload.requestId).toBe("req-abc");
  });

  it("transitions to the success state on a 201", async () => {
    vi.spyOn(api.contacts, "submit").mockResolvedValueOnce({
      id: "row-1",
      received_at: "2026-07-01T00:00:00Z",
    });

    const { getByRole, getAllByRole, findByText, queryByRole } = render(
      <ContactForm />,
    );
    fillValid(getAllByRole);
    fireEvent.click(getByRole("button", { name: /enviar mensaje/i }));

    // The success view replaces the form, so the textbox inputs
    // disappear. The localized "gracias" copy is what we look for.
    const ok = await findByText(/gracias/i);
    expect(ok).toBeTruthy();
    // The submit button should be gone (form replaced).
    expect(queryByRole("button", { name: /enviar mensaje/i })).toBeNull();
  });

  it("does not call the api when validation fails", async () => {
    const submit = vi.spyOn(api.contacts, "submit");

    const { getByRole, getAllByRole, findByText } = render(<ContactForm />);
    // Leave the name empty.
    const inputs = getAllByRole("textbox");
    fireEvent.input(inputs[1], { target: { value: "alice@example.com" } });
    fireEvent.input(inputs[2], { target: { value: "Hello" } });
    fireEvent.input(inputs[3], {
      target: { value: "This is a valid message body of sufficient length." },
    });

    fireEvent.click(getByRole("button", { name: /enviar mensaje/i }));

    // Inline error for the required name field.
    await findByText(/este campo es obligatorio/i);
    expect(submit).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// i18n switch
// ---------------------------------------------------------------------------

describe("ContactForm i18n", () => {
  it("re-renders labels when <html data-lang> flips to 'en'", async () => {
    document.documentElement.setAttribute("data-lang", "es");
    const { getByLabelText, findByLabelText } = render(<ContactForm />);

    // Spanish label for the name field.
    expect(getByLabelText(/nombre/i)).toBeTruthy();

    // Flip the language.
    document.documentElement.setAttribute("data-lang", "en");

    // English label re-resolves in place.
    const nameInput = await findByLabelText(/name/i);
    expect(nameInput).toBeTruthy();
    // And the submit button text changes too.
    expect(document.body.textContent).toMatch(/send message/i);
  });
});
