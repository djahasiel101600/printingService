"""Backfill the sales ledger from payments that already moved money.

The ledger is written from the moment a payment is confirmed, but rows that
predate it would be invisible to the sales dashboard. One entry per
PAID/REFUNDED payment (at paid_at) plus a matching refund entry where the
payment was already refunded — exactly what the hooks would have written.
Re-runnable: hit ``SalesEntry.objects.exists()`` first, and get_or_create
respects the (payment, kind) unique constraint.
"""
from django.db import migrations


def backfill(apps, schema_editor):
    Payment = apps.get_model("payments", "Payment")
    SalesEntry = apps.get_model("payments", "SalesEntry")
    if SalesEntry.objects.exists():
        return
    for payment in Payment.objects.filter(status__in=["paid", "refunded"]).iterator():
        SalesEntry.objects.get_or_create(
            payment=payment, kind="payment",
            defaults={
                "order_id": payment.order_id,
                "amount": payment.amount,
                "method": payment.method or "qrph",
                "tracking_id": payment.order.tracking_id,
                "reason": ((payment.raw_response or {}).get("recorded_by") or "")[:64],
                "occurred_at": payment.paid_at or payment.created_at,
            },
        )
        if payment.status == "refunded":
            SalesEntry.objects.get_or_create(
                payment=payment, kind="refund",
                defaults={
                    "order_id": payment.order_id,
                    "amount": payment.amount,
                    "method": payment.method or "qrph",
                    "tracking_id": payment.order.tracking_id,
                    "reason": "backfill",
                    "occurred_at": payment.updated_at,
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0003_salesentry"),
    ]
    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
