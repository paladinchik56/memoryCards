from django.urls import path

from . import views

app_name = 'api'

urlpatterns = [
    path('auth/token/', views.auth_token, name='token'),
    path('auth/logout/', views.auth_logout, name='logout'),
    path('me/', views.me, name='me'),
    path('scheduler/', views.scheduler, name='scheduler'),
    path('library/', views.library, name='library'),
    path('shared/<uuid:token>/', views.shared_collection, name='shared'),
    path('shared/<uuid:token>/take/', views.take, name='take'),
    path('sync/', views.sync, name='sync'),
]
