from django.urls import path
from .views import HomePage, Dashboard, AboutPage, ScrapeInfo, Summary_stat

urlpatterns = [
    path('', HomePage, name = 'home'),
    path('scrape/', ScrapeInfo, name= 'scrape'),
    path('stat/', Summary_stat, name='stat'),
    path('dashboard/', Dashboard, name = 'dashboard'),
    path('about/', AboutPage, name = 'about'),
]
