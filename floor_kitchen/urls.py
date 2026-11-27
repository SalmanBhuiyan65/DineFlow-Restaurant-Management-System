"""URL routes for Floor Map, Order Entry, and Kitchen Display (Member 1: Salman)."""

from django.urls import path

from floor_kitchen import views

app_name = 'floor_kitchen'

urlpatterns = [
    path('', views.floor_dashboard, name='floor_dashboard'),
    path('orders/', views.orders_dashboard, name='orders_dashboard'),
    path('floor/partial/', views.floor_partial, name='floor_partial'),
    path('table/<int:table_id>/seat/', views.seat_table, name='seat_table'),
    path('session/<int:session_id>/add-item/', views.add_order_item, name='add_order_item'),
    path('order-item/<int:item_id>/remove/', views.remove_order_item, name='remove_order_item'),
    path('session/<int:session_id>/send-kitchen/', views.send_to_kitchen, name='send_to_kitchen'),
    path('session/<int:session_id>/request-bill/', views.request_bill, name='request_bill'),
    path('kitchen/', views.kitchen_display, name='kitchen_display'),
    path('kitchen/partial/', views.kitchen_partial, name='kitchen_partial'),
    path('kitchen/bump/<int:ticket_id>/', views.bump_ticket, name='bump_ticket'),
]
