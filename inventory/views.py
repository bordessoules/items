from django.shortcuts import render
from django.views.generic import ListView, DetailView
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
import re
from .models import Item, QRCode, Label, Email, Attachment
from .serializers import (
    ItemSerializer, QRCodeSerializer, LabelSerializer,
    EmailSerializer, AttachmentSerializer
)

class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.prefetch_related('qr_codes', 'labels', 'emails', 'attachments')
    serializer_class = ItemSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['description', 'labels__name']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    @action(detail=True, methods=['post'])
    def add_qr_code(self, request, pk=None):
        item = self.get_object()
        code = request.data.get('code')
        if not code:
            return Response(
                {'error': 'QR code is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if QR code already exists
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
    def add_label(self, request, pk=None):
        item = self.get_object()
        label_name = request.data.get('name')
        if not label_name:
            return Response(
                {'error': 'Label name is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        label, _ = Label.objects.get_or_create(name=label_name)
        item.labels.add(label)
        return Response(LabelSerializer(label).data)

class QRCodeViewSet(viewsets.ModelViewSet):
    queryset = QRCode.objects.all()
    serializer_class = QRCodeSerializer
    filter_backends = [SearchFilter]
    search_fields = ['code']

class LabelViewSet(viewsets.ModelViewSet):
    queryset = Label.objects.all()
    serializer_class = LabelSerializer
    filter_backends = [SearchFilter]
    search_fields = ['name']

class EmailViewSet(viewsets.ModelViewSet):
    """ViewSet for handling Email operations."""
    queryset = Email.objects.prefetch_related('attachments')
    serializer_class = EmailSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['subject', 'sender']
    ordering_fields = ['sent_at', 'created_at']
    ordering = ['-sent_at']

    @action(detail=False, methods=['post'])
    def process_unhandled(self, request):
        """Create items from unprocessed emails with QR codes in subject."""
        unhandled = self.get_queryset().filter(item__isnull=True)
        stats = {'total': unhandled.count(), 'created': 0, 'skipped': 0}
        skipped = []

        try:
            with transaction.atomic():
                for email in unhandled:
                    result = self._process_email(email)
                    if result.get('created'):
                        stats['created'] += 1
                    else:
                        stats['skipped'] += 1
                        skipped.append(result['skip_info'])

            return Response({
                'stats': stats,
                'skipped': skipped
            })

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _process_email(self, email: Email) -> dict:
        """Process a single email and return result."""
        # Skip replies
        if email.subject.lower().startswith('re:'):
            return {
                'skip_info': {
                    'email': email.email_uid,
                    'reason': 'reply',
                    'subject': email.subject
                }
            }

        # Extract QR code
        qr_match = re.search(r'\b(\d{5})\b', email.subject or '')
        if not qr_match:
            return {
                'skip_info': {
                    'email': email.email_uid,
                    'reason': 'no_qr_code',
                    'subject': email.subject
                }
            }

        qr_code = qr_match.group(1)
        
        # Skip if QR exists
        if QRCode.objects.filter(code=qr_code).exists():
            return {
                'skip_info': {
                    'email': email.email_uid,
                    'reason': 'existing_qr',
                    'qr': qr_code
                }
            }

        # Create item and link
        item = Item.objects.create(description=email.subject.strip())
        QRCode.objects.create(item=item, code=qr_code)
        email.item = item
        email.save()

        return {'created': True}

class AttachmentViewSet(viewsets.ModelViewSet):
    queryset = Attachment.objects.all()
    serializer_class = AttachmentSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ['filename']
    filterset_fields = ['content_type']

class EmailListView(ListView):
    model = Email
    template_name = 'inventory/email_list.html'
    context_object_name = 'emails'
    paginate_by = 20
    ordering = ['-sent_at']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_emails'] = Email.objects.count()
        context['total_attachments'] = Attachment.objects.count()
        return context

class EmailDetailView(DetailView):
    model = Email
    template_name = 'inventory/email_detail.html'
    context_object_name = 'email'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        email = self.get_object()
        context['attachments'] = email.attachments.all()
        return context