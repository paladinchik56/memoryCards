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
    path('collections/view/<uuid:token>/take/', views.collection_take, name='collection_take'),
    path('collections/<int:pk>/', views.collection_detail, name='collection_detail'),
    path('collections/<int:pk>/visibility/', views.collection_set_visibility, name='collection_set_visibility'),
    path('study/', views.study_topics, name='study_topics'),
    path('study/<int:pk>/', views.study_choose, name='study_choose'),
    path('study/<int:pk>/start/', views.run_start, name='run_start'),
    path('study/<int:pk>/run/', views.topic_run, name='topic_run'),
    path('study/<int:pk>/run/grade/', views.run_grade, name='run_grade'),
    path('study/<int:pk>/run/next-round/', views.run_next_round, name='run_next_round'),
    path('study/<int:pk>/run/reset/', views.run_reset, name='run_reset'),
]
