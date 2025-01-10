"""
Views for the inventory management system.
Includes both list and detail views with HTMX enhancements.
"""

from logging import warning
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.db.models import Prefetch, Count, Subquery, OuterRef
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.core.management import call_command
from django.http import JsonResponse

from .models import AIImgdescription, AIdescription, Item, Email, Attachment, Label

# Base Views
class BaseListView(ListView):
    """Base list view with common functionality."""
    paginate_by = 25
    
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
        queryset = (Email.objects
                   .prefetch_related(
                       Prefetch('attachments'),
                       Prefetch('item'),
                   )
                   .order_by('-sent_at'))
        
        # Handle search if implemented
        search = self.request.GET.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(subject__icontains=search) |
                Q(from_address__icontains=search) |
                Q(body__icontains=search) |
                Q(item__qr_codes__code__icontains=search) |
                Q(item__labels__name__icontains=search) |
                Q(attachments__name__icontains=search)
            ).distinct()
            
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add additional context for email list."""
        context = super().get_context_data(**kwargs)
        context.update({
            'total_count': Email.objects.count(),
            'with_attachments_count': Email.objects.filter(attachments__isnull=False).distinct().count(),
            'with_items_count': Email.objects.filter(item__isnull=False).count(),
        })
        return context

class ItemListView(BaseListView):
    """Display list of inventory items."""
    model = Item
    template_name = 'inventory/item_list.html'
    partial_template_name = 'inventory/partials/item_list.html'
    context_object_name = 'items'

    def get_queryset(self):
        # Get base queryset of all items with prefetched related data
        queryset = Item.objects.prefetch_related(
            Prefetch('attachments'),
            'labels',
            'qr_codes',
            'emails'
        ).order_by('-created_at')  # Add default ordering by creation date, newest first
        
        search_query = self.request.GET.get('q')
        
        if search_query:
            # Filter items by multiple fields across related models
            queryset = (queryset.filter(
                Q(description__icontains=search_query) |
                Q(attachments__ai_description__icontains=search_query) |
                Q(qr_codes__code__icontains=search_query) |
                Q(labels__name__icontains=search_query) |
                Q(emails__subject__icontains=search_query) |
                Q(emails__sender__icontains=search_query)
            )
            .select_related('attachments')
            .distinct())
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add labels to context for the dropdown and handle AI descriptions."""
        context = super().get_context_data(**kwargs)
        context['all_labels'] = Label.objects.all().order_by('name')

        # Add AI description display handling
        for item in context.get('object_list', []):
            latest_ai_desc = item.item_ai_descriptions.order_by('-created_at').first()
            item.truncated_description = latest_ai_desc.response[:150] if latest_ai_desc else ''
            item.needs_generation = not bool(latest_ai_desc)
    
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
    """Enhanced email detail view with related data."""
    model = Email
    template_name = 'inventory/email_detail.html'
    partial_template_name = 'inventory/partials/email_detail_modal.html'
    context_object_name = 'email'

    def get_object(self):
        """Get email with optimized prefetching."""
        return (Email.objects
                .prefetch_related(
                    'attachments',
                    'item__labels',
                    'item__qr_codes'
                )
                .select_related('item')
                .get(pk=self.kwargs['pk']))

    def get_context_data(self, **kwargs):
        """Add additional context for email detail."""
        context = super().get_context_data(**kwargs)
        context['related_emails'] = []
        if self.object.item:
            context['related_emails'] = (
                Email.objects
                .filter(item=self.object.item)
                .exclude(pk=self.object.pk)
                .order_by('-sent_at')[:5]
            )
        return context

class ItemDetailView(BaseDetailView):
    """Display detailed view of an item."""
    model = Item
    template_name = 'inventory/item_detail.html'
    partial_template_name = 'inventory/partials/item_detail_modal.html'
    context_object_name = 'item'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get latest image descriptions
        latest_descriptions = AIImgdescription.objects.filter(
            attachment__item=self.object,
            created_at=Subquery(
                AIImgdescription.objects.filter(
                    attachment=OuterRef('attachment')
                ).order_by('-created_at').values('created_at')[:1]
            )
        )
        context['latest_descriptions'] = {
            desc.attachment_id: desc for desc in latest_descriptions
        }
        # Get latest text descriptions
        latest_text_descriptions = AIdescription.objects.filter(
            item=self.object,
            created_at=Subquery(
                AIdescription.objects.filter(
                    item=OuterRef('item')
                ).order_by('-created_at').values('created_at')[:1]
            )
        )
        context['latest_text_descriptions'] = {
            desc.item_id: desc for desc in latest_text_descriptions
        }
        return context

    def get_object(self):
        """Get item with related data prefetched."""
        return (Item.objects
                .prefetch_related('labels', 'qr_codes', 
                                'attachments', 'emails')
                .get(pk=self.kwargs['pk']))
    
@require_http_methods(["POST"])
def generate_listing(request, item_id):
    """Handle POST request for listing generation"""
    item = get_object_or_404(Item, pk=item_id)
    descriptions = "\n".join([
        desc.response for desc in item.item_ai_descriptions.all()
    ])
    
    from .services.text import handle_listing_generation
    listing_data = handle_listing_generation(descriptions)
    
    if listing_data:
        return render(request, 'inventory/partials/generated_listing.html', {
            'listing': listing_data,
            'item': item
        })
    return HttpResponse(
        "Échec de la génération de l'annonce", 
        status=400
        )

# HTMX Handlers
@require_http_methods(["GET"])
def image_preview(request, attachment_id):
    """Show image preview in modal with navigation."""
    attachment = get_object_or_404(Attachment, pk=attachment_id)
    source_type = request.GET.get('source_type')
    source_id = request.GET.get('source_id')
    latest_ai_desc = attachment.attachment_ai_descriptions.order_by('-created_at').first()

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
        'latest_description': latest_ai_desc,
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
        
        # Simplified context - no need for the HX-Trigger check
        context = {
            'item': item,
            'all_labels': Label.objects.all().order_by('name')
        }
        
        response = render(request, 'inventory/partials/item_label_section.html', context)
        response['HX-Trigger'] = 'refreshLabels'  # Add this line
        return response
        
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
def get_label_section(request, item_id):
    """Get updated label section for an item."""
    item = get_object_or_404(Item, pk=item_id)
    context = {
        'item': item,
        'all_labels': Label.objects.all().order_by('name')
    }
    return render(request, 'inventory/partials/item_label_section.html', context)

@require_http_methods(["GET"])
def search_items(request):
    """Search items and return results."""
    query = request.GET.get('q', '')
    print(f"Search query: {query}")
    
    items = (Item.objects
             .prefetch_related(
                 'attachments__attachment_ai_descriptions',  # Follows Item -> Attachment -> AIdescription
                 'labels',                      # Gets all labels for each item
                 'qr_codes',                    # Gets all QR codes for each item
                 'emails'                       # Gets all emails for each item
             )
             .filter(
                 Q(description__icontains=query) |
                 Q(ai_aggregated_description__icontains=query) | 
                 Q(attachments__attachment_ai_descriptions__response__icontains=query) |
                 Q(qr_codes__code__icontains=query) |
                 Q(labels__name__icontains=query) |
                 Q(emails__subject__icontains=query) |
                 Q(emails__sender__icontains=query)
             )
             .distinct().order_by('-created_at'))
    
    print(f"SQL Query: {items.query}")
    print(f"Results count: {items.count()}")
    
    return render(request, 'inventory/partials/item_list.html', 
                 {'items': items, 'htmx': True})

@require_http_methods(["GET"])
def search_emails(request):
    """Search emails and return results in HTML format."""
    query = request.GET.get('q', '').strip()
    emails = (Email.objects
             .filter(
                 Q(subject__icontains=query) |
                 Q(sender__icontains=query) |
                 Q(body__icontains=query)
             )
             .prefetch_related('attachments')
             .select_related('item')
             .order_by('-sent_at')[:10])
    
    return render(request, 'inventory/partials/email_list.html', 
                 {'emails': emails})

@require_http_methods(["GET"])
def email_detail_modal(request, email_id):
    """Show email detail in modal."""
    email = get_object_or_404(
        Email.objects
        .prefetch_related('attachments', 'item__labels')
        .select_related('item'),
        pk=email_id
    )
    
    context = {
        'email': email,
        'related_emails': (
            Email.objects
            .filter(item=email.item)
            .exclude(pk=email.pk)
            .order_by('-sent_at')[:5]
            if email.item else []
        )
    }
    
    return render(request, 'inventory/partials/email_detail_modal.html', context)

@require_http_methods(["GET"])
def email_detail_modal(request, email_id):
    """Show email detail in modal."""
    email = get_object_or_404(
        Email.objects
        .prefetch_related('attachments', 'item__labels')
        .select_related('item'),
        pk=email_id
    )
    
    context = {
        'email': email,
        'related_emails': (
            Email.objects
            .filter(item=email.item)
            .exclude(pk=email.pk)
            .order_by('-sent_at')[:5]
            if email.item else []
        )
    }
    
    return render(request, 'inventory/partials/email_detail_modal.html', context)

@require_http_methods(["POST"])
def refresh_ai_analysis(request, item_id):
    try:
        call_command('update_item_descriptions', str(item_id), force=True)
        item = get_object_or_404(Item, pk=item_id)
        latest_desc = item.item_ai_descriptions.order_by('-created_at').first()

        return render(request, 'inventory/partials/ai_description.html', {
            'description': latest_desc.response if latest_desc else '',
            'item': item
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["POST"])
def refresh_attachment_ai(request, attachment_id):
    try:
        attachment = get_object_or_404(Attachment, pk=attachment_id)
        response = attachment.query_vision_ai("pixtral-12b-2409", "Décris uniquement...")
        return render(request, 'inventory/partials/attachment_ai_description.html', {
            'description': response,
            'attachment': attachment
        })
    except Exception as e:
        warning('error:' + str(e))
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(["POST"])
def generate_image_description(request, attachment_id):
    attachment = get_object_or_404(Attachment, id=attachment_id)
    try:
        response = attachment.query_vision_ai("pixtral-12b-2409", "Décris uniquement l'objet principal de cette image de manière factuelle (dimensions, couleurs, forme, matériau). Liste ensuite tous les textes et codes-barres visibles mot pour mot, sans interprétation. Ignore l'arrière-plan et toute personne présente dans l'image.")
        
        return render(request, 'inventory/partials/attachment_ai_description.html', {
            'description': response,
            'attachment': attachment
        })
    except Exception as e:
        warning('error:' + str(e))
        return JsonResponse({'error': str(e)}, status=500)

