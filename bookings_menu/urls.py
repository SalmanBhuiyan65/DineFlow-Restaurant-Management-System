"""URL routes for Reservations, Waitlist, and Menu Catalog (Member 2: Orin)."""

from django.urls import path

from bookings_menu import views

app_name = 'bookings_menu'

urlpatterns = [
    path('bookings/', views.bookings_dashboard, name='bookings_dashboard'),
    path('waitlist/', views.waitlist_dashboard, name='waitlist_dashboard'),
    path('bookings/create/', views.create_reservation, name='create_reservation'),
    path(
        'bookings/<int:reservation_id>/seat/',
        views.seat_reservation,
        name='seat_reservation',
    ),
    path(
        'bookings/<int:reservation_id>/status/<str:status>/',
        views.mark_reservation_status,
        name='mark_reservation_status',
    ),
    path('waitlist/add/', views.add_walkin, name='add_walkin'),
    path(
        'waitlist/<int:entry_id>/seat/',
        views.seat_waitlist_entry,
        name='seat_waitlist_entry',
    ),
    path('menu/', views.menu_catalog, name='menu_catalog'),
    path('menu/create/', views.create_menu_item, name='create_menu_item'),
    path(
        'menu/<int:item_id>/toggle/',
        views.toggle_menu_item,
        name='toggle_menu_item',
    ),
    path('customers/', views.customers_dashboard, name='customers_dashboard'),
    path('customers/create/', views.create_customer, name='create_customer'),
]
