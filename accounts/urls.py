"""URL routes for staff authentication and demo role switching."""

from django.urls import path

from accounts import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('switch-role/<str:role>/', views.switch_role, name='switch_role'),
]
