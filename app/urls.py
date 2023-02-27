from django.urls import path
from . import views

urlpatterns = [
    path('home', views.home, name='home'),
    path('', views.login, name='login'),
    path('checkout', views.jobquery_web, name='checkout'),
    path('checkout_api', views.jobquery_api, name='checkout_api')
]
