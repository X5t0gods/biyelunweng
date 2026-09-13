from django.urls import path

from apps.purchase import views

app_name = 'purchase'

urlpatterns = [
    path('', views.order_list, name='order_list'),
    path('create/', views.order_create, name='order_create'),
    path('<int:pk>/', views.order_detail, name='order_detail'),
    path('<int:pk>/add-item/', views.order_add_item, name='order_add_item'),
    path('<int:pk>/item/<int:item_pk>/delete/', views.order_delete_item, name='order_delete_item'),
    path('<int:pk>/confirm/', views.order_confirm, name='order_confirm'),
    path('<int:pk>/cancel/', views.order_cancel, name='order_cancel'),
    path('<int:pk>/delete/', views.order_delete, name='order_delete'),
]
