from django.urls import path

from . import views

app_name = 'cards'

urlpatterns = [
    path('', views.card_list, name='list'),
    path('<int:pk>/edit/', views.card_edit, name='edit'),
    path('<int:pk>/delete/', views.card_delete, name='delete'),
    path('test-mode/toggle/', views.toggle_test_mode, name='toggle_test_mode'),
    path('review/', views.review, name='review'),
    path('review/<int:pk>/grade/', views.review_grade, name='grade'),
    path('review/undo/', views.review_undo, name='undo'),
]
