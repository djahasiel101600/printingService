from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    """Append-only audit trail of staff/admin activity.

    Written by ``log_activity`` from every admin write endpoint (order
    actions, deletion, notes/spec edits, pricing, staff management) and
    never mutated or deleted. ``actor``/``object`` use SET_NULL while
    ``actor_email``/``object_repr`` are snapshots, so entries stay
    meaningful after the account or the object itself is gone — deleting
    an order leaves an "order.delete" row pointing at its tracking ID,
    not a hole in the history.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="activity_logs",
    )
    actor_email = models.CharField(max_length=255, blank=True)  # snapshot
    # Dotted verb, namespaced by area: "order.approve", "order.delete",
    # "pricing_rule.update", "staff.deactivate", "pricing_settings.update"…
    action = models.CharField(max_length=64, db_index=True)
    object_type = models.CharField(max_length=32, db_index=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    object_repr = models.CharField(max_length=255)  # snapshot (tracking id, email…)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        who = self.actor_email or "system"
        return f"{who}: {self.action} → {self.object_repr}"
