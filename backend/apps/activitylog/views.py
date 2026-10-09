from datetime import datetime

from django.db.models import Q
from rest_framework import permissions, serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.pricing.views import IsShopAdmin

from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ["id", "actor_email", "action", "object_type", "object_id",
                  "object_repr", "detail", "created_at"]
        read_only_fields = fields


class ActivityLogView(APIView):
    """Owner-only audit feed: who did what, newest first (paginated).

    Filters: ``action`` matches by prefix (``order`` or ``order.approve``),
    ``search`` covers object/actor/detail, ``from``/``to`` are YYYY-MM-DD
    dates on the day the entry was written.
    """

    permission_classes = [permissions.IsAuthenticated, IsShopAdmin]

    def get(self, request):
        entries = ActivityLog.objects.all()

        action = (request.query_params.get("action") or "").strip()
        if action:
            entries = entries.filter(action__startswith=action)

        search = (request.query_params.get("search") or "").strip()
        if search:
            entries = entries.filter(
                Q(object_repr__icontains=search)
                | Q(actor_email__icontains=search)
                | Q(detail__icontains=search)
            )

        raw_from = (request.query_params.get("from") or "").strip()
        raw_to = (request.query_params.get("to") or "").strip()
        try:
            if raw_from:
                entries = entries.filter(
                    created_at__date__gte=datetime.strptime(raw_from, "%Y-%m-%d").date())
            if raw_to:
                entries = entries.filter(
                    created_at__date__lte=datetime.strptime(raw_to, "%Y-%m-%d").date())
        except ValueError:
            return Response({"detail": "Dates must be formatted YYYY-MM-DD."}, status=400)

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(entries, request)
        return paginator.get_paginated_response(
            ActivityLogSerializer(page, many=True).data)
