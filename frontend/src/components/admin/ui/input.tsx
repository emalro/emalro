/**
 * shadcn/ui Input primitive (admin SPA).
 *
 * Plain `<input>` with the data-terminal style. Forwarded ref so
 * react-hook-form / TanStack form integrations can focus the
 * field programmatically.
 */
import * as React from "react";

import { cn } from "../../../lib/cn";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-9 w-full rounded-md border border-border bg-bg-surface px-3 py-1 text-sm text-ink-primary shadow-sm transition-colors placeholder:text-ink-tertiary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        ref={ref}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

export { Input };
