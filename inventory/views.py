"""
Views for the inventory management system.
Includes both list and detail views with HTMX enhancements.
"""

from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.db.models import Prefetch, Count
from django.core.paginator import Paginator
from django.db import transaction

from .models import Item, Email, Attachment, Label, QRCode

# Base Views
class BaseListView(ListView):
    """Base list view with common functionality."""
    paginate_by = 50
    
    def get_template_names(self):
        """Return appropriate template based on request type."""
        if self.request.headers.get('HX-Request'):
            return [self.partial_template_name]
        return [self.template_name]

class BaseDetailView(DetailView):
    """Base detail view with common functionality."""
    def get_template_names(self):
        """Return appropriate template based on request type."""
        if self.request.headers.get('HX-Request'):
            return [self.partial_template_name]
        return [self.template_name]

# List Views
class EmailListView(BaseListView):
    """Display list of emails with attachments."""
    model = Email
    template_name = 'inventory/email_list.html'
    partial_template_name = 'inventory/partials/email_list.html'
    context_object_name = 'emails'

    def get_queryset(self):
        """Get emails with related data prefetched."""
        return (Email.objects
                .prefetch_related('attachments')
                .select_related('item')
                .order_by('-sent_at'))

class ItemListView(BaseListView):
    """Display list of inventory items."""
    model = Item
    template_name = 'inventory/item_list.html'
    partial_template_name = 'inventory/partials/item_list.html'
    context_object_name = 'items'

    def get_queryset(self):
        """Get items with related data prefetched."""
        return (Item.objects
                .prefetch_related('labels', 'qr_codes', 
                                'attachments', 'emails')
                .order_by('-created_at'))

    def get_context_data(self, **kwargs):
        """Add labels to context for the dropdown."""
        context = super().get_context_data(**kwargs)
        context['all_labels'] = Label.objects.all().order_by('name')
        return context

class LabelListView(BaseListView):
    """Display list of labels with their associated items."""
    model = Label
    template_name = 'inventory/label_list.html'
    partial_template_name = 'inventory/partials/label_list.html'
    context_object_name = 'labels'

    def get_queryset(self):
        """Get labels with related items prefetched."""
        return (Label.objects
                .prefetch_related('items')
                .annotate(item_count=Count('items'))
                .order_by('name'))

class AttachmentListView(BaseListView):
    """Display a filterable grid of attachments."""
    model = Attachment
    template_name = 'inventory/attachment_list.html'
    partial_template_name = 'inventory/partials/attachment_list.html'
    context_object_name = 'attachments'
    paginate_by = 24  # 6x4 grid looks nice

    def get_queryset(self):
        """Get filtered attachments."""
        queryset = (Attachment.objects
                   .select_related('item', 'email')
                   .order_by('-created_at'))
        
        # Handle filtering
        file_type = self.request.GET.get('type', 'all')
        if file_type == 'images':
            queryset = queryset.filter(content_type__startswith='image/')
        elif file_type == 'documents':
            queryset = queryset.filter(
                content_type__in=['application/pdf', 'application/msword', 
                                'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
            )
        
        # Handle search
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(filename__icontains=search)
            
        return queryset

    def get_context_data(self, **kwargs):
        """Add filtering context."""
        context = super().get_context_data(**kwargs)
        context.update({
            'current_type': self.request.GET.get('type', 'all'),
            'search_query': self.request.GET.get('search', ''),
            'total_count': Attachment.objects.count(),
            'image_count': Attachment.objects.filter(content_type__startswith='image/').count(),
            'document_count': Attachment.objects.filter(
                content_type__in=['application/pdf', 'application/msword']
            ).count()
        })
        return context

# Detail Views
class EmailDetailView(BaseDetailView):
    """Display detailed view of an email."""
    model = Email
    template_name = 'inventory/email_detail.html'
    partial_template_name = 'inventory/partials/email_detail.html'
    context_object_name = 'email'

    def get_object(self):
        """Get email with related data prefetched."""
        return (Email.objects
                .prefetch_related('attachments')
                .select_related('item')
                .get(pk=self.kwargs['pk']))

class ItemDetailView(BaseDetailView):
    """Display detailed view of an item."""
    model = Item
    template_name = 'inventory/item_detail.html'
    partial_template_name = 'inventory/partials/item_detail_modal.html'
    context_object_name = 'item'

    def get_object(self):
        """Get item with related data prefetched."""
        return (Item.objects
                .prefetch_related('labels', 'qr_codes', 
                                'attachments', 'emails')
                .get(pk=self.kwargs['pk']))

# HTMX Handlers
@require_http_methods(["GET"])
def image_preview(request, attachment_id):
    """Show image preview in modal with navigation."""
    attachment = get_object_or_404(Attachment, pk=attachment_id)
    source_type = request.GET.get('source_type')
    source_id = request.GET.get('source_id')
    
    if source_type == 'email' and source_id:
        all_images = list(Attachment.objects.filter(
            email_id=source_id,
            content_type__startswith='image/'
        ).order_by('id'))
    elif source_type == 'item' and source_id:
        all_images = list(Attachment.objects.filter(
            item_id=source_id,
            content_type__startswith='image/'
        ).order_by('id'))
    else:
        all_images = [attachment]
    
    try:
        current_index = all_images.index(attachment)
        prev_image = all_images[current_index - 1] if current_index > 0 else None
        next_image = all_images[current_index + 1] if current_index < len(all_images) - 1 else None
    except ValueError:
        prev_image = next_image = None
    
    context = {
        'attachment': attachment,
        'prev_image': prev_image,
        'next_image': next_image,
        'source_type': source_type,
        'source_id': source_id,
        'current_index': current_index + 1,
        'total_images': len(all_images)
    }
    
    return render(request, 'inventory/partials/image_preview_modal.html', context)
@require_http_methods(["POST"])
def create_label(request):
    """Create a new label and return updated labels list."""
    name = request.POST.get('name')
    if not name:
        return HttpResponse("Label name is required", status=400)
    
    try:
        Label.objects.create(name=name)
        # Get updated labels with count
        labels = (Label.objects
                 .prefetch_related('items')
                 .annotate(item_count=Count('items'))
                 .order_by('name'))
        
        return render(request, 'inventory/partials/label_list.html',
                     {'labels': labels})
    except Exception as e:
        return HttpResponse(str(e), status=400)

@require_http_methods(["POST"])
def quick_create_label(request, item_id):
    """Create a new label and add it to an item."""
    name = request.POST.get('name')
    if not name:
        return HttpResponse("Label name is required", status=400)
    
    try:
        with transaction.atomic():
            label, created = Label.objects.get_or_create(name=name.strip())
            item = get_object_or_404(Item, pk=item_id)
            item.labels.add(label)
            
        context = {
            'item': item,
            'all_labels': Label.objects.all().order_by('name')
        }
        return render(request, 'inventory/partials/item_label_section.html', context)
    except Exception as e:
        return HttpResponse(str(e), status=400)

@require_http_methods(["POST"])
def add_label_to_item(request, item_id):
    """Add a label to an item."""
    item = get_object_or_404(Item, pk=item_id)
    label_id = request.POST.get('label_id')    
    try:
        if label_id:
            label = get_object_or_404(Label, pk=label_id)
            item.labels.add(label)
            
        context = {
            'item': item,
            'all_labels': Label.objects.all().order_by('name')
        }
        return render(request, 'inventory/partials/item_label_section.html', context)
    except Exception as e:
        return HttpResponse(str(e), status=400)

@require_http_methods(["DELETE", "POST"])
def remove_label_from_item(request, item_id, label_id):
    """Remove a label from an item."""
    try:
        with transaction.atomic():
            item = get_object_or_404(Item, pk=item_id)
            label = get_object_or_404(Label, pk=label_id)
            item.labels.remove(label)
        
        context = {
            'item': item,
            'all_labels': Label.objects.all().order_by('name')
        }
        return render(request, 'inventory/partials/item_label_section.html', context)
    except Exception as e:
        return HttpResponse(str(e), status=400)

@require_http_methods(["DELETE"])
def delete_label(request, label_id):
    """Delete a label."""
    label = get_object_or_404(Label, id=label_id)
    try:
        label.delete()
        return HttpResponse("", status=200)
    except Exception as e:
        return HttpResponse(str(e), status=400)

@require_http_methods(["GET"])
def search_items(request):
    """Search items and return results."""
    query = request.GET.get('q', '')
    items = (Item.objects
             .filter(description__icontains=query)
             .prefetch_related('labels', 'attachments')[:10])
    
    return render(request, 'inventory/partials/item_list.html', 
                 {'items': items, 'htmx': True})