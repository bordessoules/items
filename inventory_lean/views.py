from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Item, Label
from .serializers import ItemSerializer
from .services.vision import VisionService
from .services.text import TextService

class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.prefetch_related('attachments', 'qr_codes', 'labels', 'emails')
    serializer_class = ItemSerializer

    @action(detail=True, methods=['post'])
    def analyze_images(self, request, pk=None):
        item = self.get_object()
        vision_service = VisionService()
        
        for attachment in item.get_images():
            if not attachment.ai_description:
                attachment.ai_description = vision_service.analyze_image(attachment.file.path)
                attachment.save()
        
        item.generate_description()
        return Response(ItemSerializer(item).data)

    @action(detail=True, methods=['post'])
    def add_label(self, request, pk=None):
        item = self.get_object()
        label, _ = Label.objects.get_or_create(name=request.data['name'])
        item.labels.add(label)
        return Response(ItemSerializer(item).data)