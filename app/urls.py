from django.urls import path
from . import views
from . import api

urlpatterns = [
    path('home', views.home, name='home'),
    path('', views.login, name='login'),
    path('checkout', views.jobquery_web, name='checkout'),
    # API (documented in Swagger)
    path('api/checkout', api.checkout_api, name='checkout_api'),
    path('api/warranty/top-parts', api.top_warranty_parts_api, name='top_warranty_parts_api'),
]
