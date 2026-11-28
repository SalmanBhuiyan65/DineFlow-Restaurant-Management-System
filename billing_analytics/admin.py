"""Admin registration for Bills, Payments, and Financial Summaries."""

from django.contrib import admin

from billing_analytics.models import (
    Bill,
    HistoricalDailySummary,
    MonthlyFinancialSummary,
    Payment,
)

admin.site.register(Bill)
admin.site.register(Payment)
admin.site.register(HistoricalDailySummary)
admin.site.register(MonthlyFinancialSummary)
