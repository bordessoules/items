from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ItemViewSet

app_name = 'inventory_lean'

router = DefaultRouter()
router.register(r'items', ItemViewSet)

urlpatterns = [
    path('', include(router.urls)),
]