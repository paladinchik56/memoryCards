from django.urls import path

from . import views

app_name = 'cards'

urlpatterns = [
    path('', views.card_list, name='list'),
    path('<int:pk>/edit/', views.card_edit, name='edit'),
    path('<int:pk>/delete/', views.card_delete, name='delete'),
    path('<int:pk>/take/', views.card_take, name='card_take'),
    path('<int:pk>/set-collection/', views.card_set_collection, name='card_set_collection'),
    path('test-mode/toggle/', views.toggle_test_mode, name='toggle_test_mode'),
    path('review/', views.review, name='review'),
    path('review/<int:pk>/grade/', views.review_grade, name='grade'),
    path('review/undo/', views.review_undo, name='undo'),
    path('collections/', views.collection_list, name='collections'),
    path('collections/library/', views.collection_library, name='library'),
    path('collections/view/<uuid:token>/', views.collection_view, name='collection_view'),
    path('collections/<int:pk>/', views.collection_detail, name='collection_detail'),
]
