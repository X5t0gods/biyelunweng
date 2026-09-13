from django.urls import path

from apps.sales import views

app_name = 'sales'

urlpatterns = [
    path('pos/', views.pos, name='pos'),
    path('', views.sale_list, name='sale_list'),
    path('<int:pk>/', views.sale_detail, name='sale_detail'),
    path('<int:pk>/void/', views.sale_void, name='sale_void'),

    path('returns/', views.return_list, name='return_list'),
    path('returns/create/', views.return_create, name='return_create'),
    path('returns/<int:pk>/', views.return_detail, name='return_detail'),
]
