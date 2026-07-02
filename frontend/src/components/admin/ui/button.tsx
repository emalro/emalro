/**
 * shadcn/ui Button primitive (admin SPA).
 *
 * Variant + size driven by `class-variance-authority`. Supports
 * `asChild` via Radix Slot so callers can render the button as an
 * `<a>` (e.g. for an in-page link) without losing the variant
 * styles.
 *
 * Imports `* as React from "react"` (shadcn canonical). The
 * preact/compat alias (in `astro.config.mjs` + `tsconfig.json`)
 * resolves this to Preact at build time.
 *
 * The data-terminal aesthetic lives in `tailwind.config.mjs`
 * CSS variables (`--background`, `--primary`, `--border`, etc.).
 */
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "../../../lib/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-bg-base transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-accent text-bg-base hover:bg-accent-hover",
        destructive: "bg-error text-ink-primary hover:opacity-90",
        outline:
          "border border-border bg-transparent text-ink-primary hover:bg-bg-surface",
        secondary: "bg-bg-elevated text-ink-primary hover:opacity-90",
        ghost: "bg-transparent text-ink-primary hover:bg-bg-surface",
        link: "bg-transparent text-accent underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-md px-6",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
