from django.urls import path

from apps.report import views

app_name = 'report'

urlpatterns = [
    path('sales/', views.sales_report, name='sales_report'),
    path('sales/export/', views.sales_export, name='sales_export'),
    path('profit/', views.profit_report, name='profit_report'),
    path('goods/', views.goods_report, name='goods_report'),
    path('stock/', views.stock_report, name='stock_report'),
]
