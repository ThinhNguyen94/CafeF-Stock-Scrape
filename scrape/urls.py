from django.urls import path
from .views import HomePage, ScrapeInfo, Summary_stat

urlpatterns = [
    path('', HomePage, name = 'home'),
    path('scrape/', ScrapeInfo, name= 'scrape'),
    path('stat/', Summary_stat, name='stat'),
]
