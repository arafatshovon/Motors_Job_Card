from django.urls import path
from . import views
from . import api

urlpatterns = [
    path('home', views.home, name='home'),
    path('', views.login, name='login'),
    path('checkout', views.jobquery_web, name='checkout'),
    # API (documented in Swagger)
    path('api/checkout', api.checkout_api, name='checkout_api'),
    path('api/bikes/search', api.search_bike_names_api, name='search_bike_names_api'),
    path('api/bikes/names', api.all_bike_names_api, name='all_bike_names_api'),
    path('api/warranty/top-parts', api.top_warranty_parts_api, name='top_warranty_parts_api'),
    path(
        'api/warranty/top-parts/for-bike-model',
        api.top_warranty_parts_for_bike_model_api,
        name='top_warranty_parts_for_bike_model_api',
    ),
    path(
        'api/warranty/top-parts/by-bike-model',
        api.top_warranty_parts_by_bike_model_api,
        name='top_warranty_parts_by_bike_model_api',
    ),
]
