from django.urls import path

from . import views

app_name = 'web'

urlpatterns = [
    path('study/', views.study, name='study'),
    path('blitz/', views.blitz_view, name='blitz'),
    path('blitz/answer/', views.blitz_answer, name='blitz_answer'),
    path('blitz/remove/', views.blitz_remove, name='blitz_remove'),
    path('blitz/undo/', views.blitz_undo, name='blitz_undo'),
    path('add/', views.add_card, name='add'),
    path('cards/', views.cards_list, name='cards'),
    path('simple/', views.simple_list, name='simple'),
    path('simple/<uuid:uuid>/', views.simple_topic, name='simple_topic'),
    path('simple/<uuid:uuid>/restart/', views.simple_restart, name='simple_restart'),
    path('simple/<uuid:uuid>/play/', views.simple_play, name='simple_play'),
    path('simple/<uuid:uuid>/answer/', views.simple_answer, name='simple_answer'),
    path('simple/<uuid:uuid>/next/', views.simple_next, name='simple_next'),
    path('library/', views.library, name='library'),
    path('library/mine/', views.topics_mine, name='mine'),
    path('library/added/', views.topics_added, name='added'),
    path('library/browse/', views.browse, name='browse'),
    path('library/none/', views.no_topic, name='no_topic'),
    path('library/new/', views.topic_edit, name='topic_new'),
    path('library/action/', views.topic_action, name='topic_action'),
    path('library/author/<str:nickname>/', views.author, name='author'),
    path('library/t/<uuid:token>/', views.topic, name='topic'),
    path('library/t/<uuid:token>/edit/', views.topic_edit, name='topic_edit'),
    path('library/t/<uuid:token>/subscribe/', views.subscribe, name='subscribe'),
    path('card/<uuid:uuid>/', views.card_detail, name='card'),
    path('profile/', views.profile, name='profile'),
    path('profile/algorithm/', views.algorithm, name='algorithm'),
    path('profile/account/', views.account, name='account'),
    path('profile/export.csv', views.export_csv, name='export'),
    path('profile/test-mode/', views.toggle_test_mode, name='test_mode'),
    path('language/', views.set_language, name='language'),
]
