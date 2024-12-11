# inventory/urls.py
"""Main URL configuration combining API and frontend routes."""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views
from . import frontend_urls

app_name = 'inventory'

# API Router setup
router = DefaultRouter()
router.register(r'items', api_views.ItemViewSet)
router.register(r'qrcodes', api_views.QRCodeViewSet)
router.register(r'labels', api_views.LabelViewSet)
router.register(r'emails', api_views.EmailViewSet)
router.register(r'attachments', api_views.AttachmentViewSet)

# Combine API routes with frontend routes
urlpatterns = router.urls + frontend_urls.urlpatterns
