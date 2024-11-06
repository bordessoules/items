# inventory/urls.py (Main URLs)
"""
Main URL configuration for the inventory application.
Includes both API and frontend URLs.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views  # Separate API views
from . import views     # Regular views

app_name = 'inventory'

# API Router setup
router = DefaultRouter()
router.register(r'items', api_views.ItemViewSet)
router.register(r'qrcodes', api_views.QRCodeViewSet)
router.register(r'labels', api_views.LabelViewSet)
router.register(r'emails', api_views.EmailViewSet)
router.register(r'attachments', api_views.AttachmentViewSet)

# Main URL patterns
urlpatterns =router.urls