/**
 * shadcn/ui Label primitive (admin SPA).
 *
 * Renders a `<label>` tied to a form control via `htmlFor`. Uses
 * the same `data-terminal` text color and monospace-friendly
 * weight as the rest of the admin SPA.
 */
import * as React from "react";

import { cn } from "../../../lib/cn";

const Label = React.forwardRef<
  HTMLLabelElement,
  React.LabelHTMLAttributes<HTMLLabelElement>
>(({ className, ...props }, ref) => (
  <label
    ref={ref}
    className={cn(
      "text-xs font-medium uppercase tracking-wide text-ink-secondary",
      className,
    )}
    {...props}
  />
));
Label.displayName = "Label";

export { Label };
