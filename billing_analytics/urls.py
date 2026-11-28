"""URL routes for Billing, Menu Engineering Analytics, and Takings (Member 3: Hasibul)."""

from django.urls import path

from billing_analytics import views

app_name = 'billing_analytics'

urlpatterns = [
    path('billing/', views.billing_dashboard, name='billing_dashboard'),
    path('billing/<int:bill_id>/print/', views.print_bill, name='print_bill'),
    path('billing/<int:bill_id>/pay/', views.pay_bill, name='pay_bill'),
    path('analytics/', views.menu_analytics, name='menu_analytics'),
    path('takings/', views.takings_report, name='takings_report'),
]
