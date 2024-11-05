from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ItemViewSet, QRCodeViewSet, LabelViewSet,
    EmailViewSet, AttachmentViewSet,
    EmailListView, EmailDetailView
)
app_name = 'inventory'

router = DefaultRouter()
router.register(r'items', ItemViewSet)
router.register(r'qrcodes', QRCodeViewSet)
router.register(r'labels', LabelViewSet)
router.register(r'emails', EmailViewSet)
router.register(r'attachments', AttachmentViewSet)

urlpatterns = router.urls