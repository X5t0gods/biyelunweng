from django.urls import path

from apps.member import views

app_name = 'member'

urlpatterns = [
    path('levels/', views.level_list, name='level_list'),
    path('levels/create/', views.level_create, name='level_create'),
    path('levels/<int:pk>/edit/', views.level_update, name='level_update'),
    path('levels/<int:pk>/delete/', views.level_delete, name='level_delete'),

    path('', views.member_list, name='member_list'),
    path('create/', views.member_create, name='member_create'),
    path('<int:pk>/', views.member_detail, name='member_detail'),
    path('<int:pk>/edit/', views.member_update, name='member_update'),
    path('<int:pk>/recharge/', views.member_recharge, name='member_recharge'),
    path('<int:pk>/toggle/', views.member_toggle, name='member_toggle'),
    path('api/search/', views.member_api, name='member_api'),
]
