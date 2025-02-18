# inventory/api_views.py
"""
API viewsets for the inventory application.
Provides REST endpoints for all models.
"""

from inventory.services.text import TextService
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.db.models import Count

from .models import Item, QRCode, Label, Email, Attachment, ListingLBC
from .serializers import (
    ItemSerializer, QRCodeSerializer, LabelSerializer,
    EmailSerializer, AttachmentSerializer, ListingLBCSerializer
)

class ItemViewSet(viewsets.ModelViewSet):
    """API endpoint for Item operations."""
    queryset = Item.objects.prefetch_related('qr_codes', 'labels', 'emails', 'attachments')
    serializer_class = ItemSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['description', 'labels__name']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def generate_listing(self, request, pk=None):
        """Generate a listing suggestion for an item"""
        item = self.get_object()
        
        # Gather all AI descriptions
        descriptions = "\n".join([
            desc.response for desc in item.item_ai_descriptions.all()
        ])
        
        # Use TextService to generate listing
        text_service = TextService()
        listing_data = text_service.generate_listing(descriptions)
        
        if listing_data:
            return Response(listing_data)
        return Response(
            {'error': 'Failed to generate listing'},
            status=status.HTTP_400_BAD_REQUEST
        )
    @action(detail=True, methods=['post'])
    def add_qr_code(self, request, pk=None):
        """Add a new QR code to an item."""
        item = self.get_object()
        code = request.data.get('code')
        if not code:
            return Response(
                {'error': 'QR code is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if QRCode.objects.filter(code=code).exists():
            return Response(
                {'error': f'QR code {code} is already assigned to another item'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            qr_code = QRCode.objects.create(item=item, code=code)
            return Response(QRCodeSerializer(qr_code).data)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
    @action(detail=True, methods=['post'])
    def add_labels(self, request, pk=None):
        """Add multiple labels to an item."""
        item = self.get_object()
        label_ids = request.data.get('label_ids', [])
        
        try:
            labels = Label.objects.filter(id__in=label_ids)
            item.labels.add(*labels)
            return Response(ItemSerializer(item).data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def remove_labels(self, request, pk=None):
        """Remove multiple labels from an item."""
        item = self.get_object()
        label_ids = request.data.get('label_ids', [])
        
        try:
            labels = Label.objects.filter(id__in=label_ids)
            item.labels.remove(*labels)
            return Response(ItemSerializer(item).data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class QRCodeViewSet(viewsets.ModelViewSet):
    """API endpoint for QRCode operations."""
    queryset = QRCode.objects.all()
    serializer_class = QRCodeSerializer
    filter_backends = [SearchFilter]
    search_fields = ['code']

class LabelViewSet(viewsets.ModelViewSet):
    """API endpoint for Label operations."""
    queryset = Label.objects.all()
    serializer_class = LabelSerializer
    filter_backends = [SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        """Include item count with labels."""
        return Label.objects.annotate(
            item_count=Count('items')
        ).order_by('name')

    @action(detail=True, methods=['post'])
    def add_to_items(self, request, pk=None):
        """Add this label to multiple items."""
        label = self.get_object()
        item_ids = request.data.get('item_ids', [])
        
        try:
            items = Item.objects.filter(id__in=item_ids)
            label.items.add(*items)
            return Response({
                'message': f'Label added to {len(items)} items',
                'affected_items': item_ids
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def remove_from_items(self, request, pk=None):
        """Remove this label from multiple items."""
        label = self.get_object()
        item_ids = request.data.get('item_ids', [])
        
        try:
            items = Item.objects.filter(id__in=item_ids)
            label.items.remove(*items)
            return Response({
                'message': f'Label removed from {len(items)} items',
                'affected_items': item_ids
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Create multiple labels at once."""
        names = request.data.get('names', [])
        created_labels = []
        errors = []
        
        for name in names:
            try:
                label, created = Label.objects.get_or_create(name=name)
                if created:
                    created_labels.append(label)
            except Exception as e:
                errors.append(f"Error creating label '{name}': {str(e)}")
        
        return Response({
            'created': LabelSerializer(created_labels, many=True).data,
            'errors': errors
        })

class EmailViewSet(viewsets.ModelViewSet):
    """API endpoint for Email operations."""
    queryset = Email.objects.prefetch_related('attachments').select_related('item')
    serializer_class = EmailSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['subject', 'sender', 'email_uid','body']
    ordering_fields = ['sent_at', 'created_at']
    ordering = ['-sent_at']

    def get_queryset(self):
        """Get emails with related data prefetched."""
        return super().get_queryset().prefetch_related(
            'attachments',
            'item__labels',
            'item__qr_codes'
        )
    @action(detail=False, methods=['get'], url_path='search-html', url_name='search-html')
    def search_html(self, request):
        """Return search results as HTML for HTMX requests."""
        queryset = self.filter_queryset(self.get_queryset())[:10]
        if request.headers.get('HX-Request'):
            return render(
                request,
                'inventory/partials/email_list.html',
                {'emails': queryset}
            )
        return Response(self.get_serializer(queryset, many=True).data)


class AttachmentViewSet(viewsets.ModelViewSet):
    """API endpoint for Attachment operations."""
    queryset = Attachment.objects.all()
    serializer_class = AttachmentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['filename']
    filterset_fields = ['content_type']

class ListingLBCViewSet(viewsets.ModelViewSet):
    """API endpoint for LeBonCoin listings operations."""
    queryset = ListingLBC.objects.all()
    serializer_class = ListingLBCSerializer

    @action(detail=False, methods=['post'])
    def generate(self, request):
        """Generate a listing suggestion from item description"""
        item_id = request.data.get('item_id')
        if not item_id:
            return Response(
                {'error': 'Item ID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        item = Item.objects.get(id=item_id)
        descriptions = "\n".join([
            desc.response for desc in item.item_ai_descriptions.all()
        ])

        from .services.text import handle_listing_generation
        listing_data = handle_listing_generation(descriptions)

        if listing_data:
            return Response(listing_data)
        return Response(
            {'error': 'Failed to generate listing'},
            status=status.HTTP_400_BAD_REQUEST
        )
