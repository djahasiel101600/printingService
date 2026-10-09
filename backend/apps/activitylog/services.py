"""Best-effort audit writer: appending a log row must never break the
action being audited (same philosophy as the email notifications)."""
import logging

from .models import ActivityLog

log = logging.getLogger(__name__)


def log_activity(actor, action, *, object_type, object_repr,
                 object_id=None, detail=""):
    """Append one audit row. Swallows and logs any failure."""
    try:
        is_authenticated = bool(getattr(actor, "is_authenticated", False))
        ActivityLog.objects.create(
            actor=actor if is_authenticated else None,
            actor_email=(getattr(actor, "email", "") or "")[:255] if is_authenticated else "",
            action=action,
            object_type=object_type,
            object_id=object_id,
            object_repr=str(object_repr or "")[:255],
            detail=detail or "",
        )
    except Exception:  # noqa: BLE001 - auditing must not break requests
        log.exception("Could not write activity log for %r", action)
