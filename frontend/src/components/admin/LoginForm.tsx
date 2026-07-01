/**
 * @jsxImportSource preact
 *
 * Admin login form.
 *
 * Mounted at `/admin` (the admin landing route). Submits
 * credentials via the auth context; on success the user is
 * redirected to `/admin/dashboard` (the route guard in App.tsx
 * handles this). On failure, the localized error message is
 * rendered inline above the submit button.
 *
 * Localized copy lives in `LOGIN_LABELS` below. Spanish is the
 * default; English is intentionally NOT shipped (admin copy is
 * Spanish-only for now; i18n follow-up is out of scope per
 * `admin-panel` open question 1). The form labels are
 * hard-coded Spanish in line with the voseo register used
 * project-wide.
 *
 * Error code → user message mapping (per `auth-jwt` envelope
 * codes):
 * - `invalid_credentials` → "Credenciales inválidas."
 * - `network_error` (status 0) → "No se pudo contactar al
 *   servidor. Revisá tu conexión."
 * - anything else → the envelope message (developer-facing
 *   string from the backend; the operator is technical and
 *   can read it).
 */
import { useState, useCallback, type JSX } from "preact/hooks";

import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";

import { useAuth } from "./AuthContext";
import { AdminApiError } from "../../lib/admin-api";

const LOGIN_LABELS = {
  pageTitle: "Acceso admin",
  pageSubtitle: "Iniciá sesión para gestionar el portfolio.",
  emailLabel: "Email",
  emailPlaceholder: "admin@emalro.com.ar",
  passwordLabel: "Contraseña",
  passwordPlaceholder: "••••••••",
  submit: "Iniciar sesión",
  submitting: "Ingresando…",
  invalidCredentials: "Credenciales inválidas.",
  networkError: "No se pudo contactar al servidor. Revisá tu conexión.",
  genericError: "Error inesperado. Intentá de nuevo.",
} as const;

function errorMessageFor(err: unknown): string {
  if (err instanceof AdminApiError) {
    if (err.code === "invalid_credentials") {
      return LOGIN_LABELS.invalidCredentials;
    }
    if (err.code === "network_error") {
      return LOGIN_LABELS.networkError;
    }
    // Fall back to the developer-facing message from the
    // backend (the operator is technical and can read it).
    return err.message || LOGIN_LABELS.genericError;
  }
  return LOGIN_LABELS.genericError;
}

export default function LoginForm(): JSX.Element {
  const { login, isLoading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = useCallback(
    async (e: Event) => {
      e.preventDefault();
      if (submitting) return;
      setError(null);
      setSubmitting(true);
      try {
        await login(email, password);
        // The route guard in App.tsx redirects to /admin/dashboard
        // when status flips to 'authenticated'. Nothing to do here.
      } catch (err) {
        setError(errorMessageFor(err));
      } finally {
        setSubmitting(false);
      }
    },
    [email, password, login, submitting],
  );

  const disabled = submitting || isLoading;

  return (
    <section class="mx-auto flex min-h-[70vh] max-w-md items-center px-6">
      <Card class="w-full">
        <CardHeader>
          <CardTitle>{LOGIN_LABELS.pageTitle}</CardTitle>
          <CardDescription>{LOGIN_LABELS.pageSubtitle}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} class="flex flex-col gap-4" noValidate>
            <div class="flex flex-col gap-1.5">
              <Label htmlFor="admin-email">{LOGIN_LABELS.emailLabel}</Label>
              <Input
                id="admin-email"
                type="email"
                autoComplete="email"
                required
                value={email}
                placeholder={LOGIN_LABELS.emailPlaceholder}
                onInput={(e) =>
                  setEmail((e.currentTarget as HTMLInputElement).value)
                }
                disabled={disabled}
              />
            </div>
            <div class="flex flex-col gap-1.5">
              <Label htmlFor="admin-password">
                {LOGIN_LABELS.passwordLabel}
              </Label>
              <Input
                id="admin-password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                placeholder={LOGIN_LABELS.passwordPlaceholder}
                onInput={(e) =>
                  setPassword((e.currentTarget as HTMLInputElement).value)
                }
                disabled={disabled}
              />
            </div>
            {error ? (
              <p
                class="rounded-md border border-error/40 bg-error/10 px-3 py-2 text-sm text-error"
                role="alert"
                aria-live="polite"
              >
                {error}
              </p>
            ) : null}
            <Button type="submit" disabled={disabled} class="w-full">
              {submitting ? LOGIN_LABELS.submitting : LOGIN_LABELS.submit}
            </Button>
          </form>
        </CardContent>
      </Card>
    </section>
  );
}
