import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * The one page header. Before this, eight pages each hand-rolled their own
 * `<h1 className="text-2xl font-bold">`, so titles, spacing and subtitle
 * treatment drifted apart. Pages now supply content, not markup.
 */
export interface PageHeaderProps {
  title: string;
  /** One line explaining the page. Omit rather than repeat the title. */
  description?: ReactNode;
  /** Buttons on the right. On mobile these wrap below the title. */
  actions?: ReactNode;
  /** Renders a back link above the title (detail pages). */
  backTo?: string;
  backLabel?: string;
  /** Small eyebrow text above the title, e.g. a tracking ID. */
  eyebrow?: ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  actions,
  backTo,
  backLabel = "Back",
  eyebrow,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn("mb-6 space-y-1", className)}>
      {backTo && (
        <Link
          to={backTo}
          className="mb-1 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronLeft className="h-4 w-4" />
          {backLabel}
        </Link>
      )}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          {eyebrow && <div className="text-sm font-medium text-muted-foreground">{eyebrow}</div>}
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          {description && (
            <div className="text-sm text-muted-foreground sm:text-base">{description}</div>
          )}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}