from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('register/verify/', views.verify_email, name='verify_email'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('friends/', views.friends, name='friends'),
    path('friends/<int:pk>/accept/', views.friend_request_accept, name='friend_request_accept'),
    path('friends/<int:pk>/decline/', views.friend_request_decline, name='friend_request_decline'),
    path('friends/<int:pk>/remove/', views.friend_remove, name='friend_remove'),
]
