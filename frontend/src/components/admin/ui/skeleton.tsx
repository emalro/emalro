/**
 * shadcn/ui Skeleton primitive (admin SPA).
 *
 * Animated placeholder for content that is loading. Used in the
 * dashboard while TanStack Query is fetching the counts; PR #6
 * reuses it for the contact inbox loading rows.
 */
import * as React from "react";

import { cn } from "../../../lib/cn";

function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-bg-elevated", className)}
      {...props}
    />
  );
}

export { Skeleton };
