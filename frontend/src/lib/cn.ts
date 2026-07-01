/**
 * Tailwind className merger.
 *
 * Combines `clsx` (conditional class joining) with `tailwind-merge`
 * (resolves conflicting Tailwind utilities — e.g. `px-2 px-4` →
 * `px-4`). Used by every shadcn/ui primitive in
 * `frontend/src/components/admin/ui/` so variants compose
 * deterministically.
 *
 * Same recipe as the canonical shadcn `cn()` helper, ported as
 * `cn.ts` (kebab-case module name; the project uses English
 * filenames per `emalro/conventions`).
 */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
