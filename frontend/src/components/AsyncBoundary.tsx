import type { ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * The one async contract. Pages used to improvise loading and errors four
 * different ways (bare skeletons, a full-page early return, a hand-rolled red
 * paragraph, or nothing at all plus a toast). Now every list/detail screen
 * declares the same three states so trust in the UI is consistent.
 *
 * `empty` is only considered when the query has actually succeeded, so a slow
 * request never flashes "nothing here yet".
 */
export interface AsyncBoundaryProps {
  isLoading: boolean;
  error?: unknown;
  /** Set true only once loading has finished, to show the empty state. */
  isEmpty?: boolean;
  skeleton?: ReactNode;
  empty?: ReactNode;
  children: ReactNode;
  /** Message shown above the retry button. */
  errorTitle?: string;
  onRetry?: () => void;
  className?: string;
}

export function AsyncBoundary({
  isLoading,
  error,
  isEmpty = false,
  skeleton,
  empty,
  children,
  errorTitle = "Something went wrong",
  onRetry,
  className,
}: AsyncBoundaryProps) {
  if (isLoading) {
    return (
      <div className={className} aria-busy="true" aria-live="polite">
        {skeleton ?? <DefaultSkeleton />}
      </div>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className={cn(
          "flex flex-col items-center gap-3 rounded-lg border border-destructive/40 bg-destructive/5 px-6 py-10 text-center",
          className,
        )}
      >
        <AlertTriangle className="h-6 w-6 text-destructive" aria-hidden="true" />
        <div className="space-y-1">
          <h3 className="font-semibold">{errorTitle}</h3>
          <p className="text-sm text-muted-foreground">{errorMessage(error)}</p>
        </div>
        {onRetry && (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="h-4 w-4" />
            Try again
          </Button>
        )}
      </div>
    );
  }

  if (isEmpty && empty) {
    return <div className={className}>{empty}</div>;
  }

  return <div className={className}>{children}</div>;
}

/** Extracts a human message from axios, an Error, or a DRF `{detail}` body. */
export function errorMessage(error: unknown): string {
  if (!error) return "Please try again.";
  if (typeof error === "string") return error;
  const candidate = error as {
    message?: string;
    detail?: string;
    response?: { data?: { detail?: string } & Record<string, unknown> };
  };
  const fieldErrors = candidate.response?.data;
  if (fieldErrors && typeof fieldErrors === "object") {
    const firstField = Object.entries(fieldErrors).find(([, value]) => Array.isArray(value));
    if (firstField) {
      const [field, messages] = firstField;
      const [message] = messages as string[];
      return `${field}: ${message}`;
    }
  }
  return candidate.response?.data?.detail ?? candidate.message ?? "Please try again.";
}

function DefaultSkeleton() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}