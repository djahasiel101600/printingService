from django.contrib import admin

from .models import Payment, PaymentSettings

admin.site.register(Payment)
admin.site.register(PaymentSettings)
