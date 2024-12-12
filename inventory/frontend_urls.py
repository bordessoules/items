# inventory/frontend_urls.py
"""Frontend URL configuration for the inventory application."""

from django.urls import path
from . import views

urlpatterns = [
    # Main views
    path('', views.ItemListView.as_view(), name='index'),
    path('emails/', views.EmailListView.as_view(), name='email_list'),
    path('items/', views.ItemListView.as_view(), name='item_list'),
    path('labels/', views.LabelListView.as_view(), name='label_list'),
    path('attachments/', views.AttachmentListView.as_view(), name='attachment_list'),

    # Add this new route for email search
    path('emails/search-html/', views.search_emails, name='email-search-html'),
    path('emails/<int:email_id>/modal/', views.email_detail_modal, name='email_detail_modal'),
    
    # Detail views
    path('emails/<int:pk>/', views.EmailDetailView.as_view(), name='email_detail'),
    path('items/<int:pk>/', views.ItemDetailView.as_view(), name='item_detail'),
    
    # HTMX handlers
    path('image-preview/<int:attachment_id>/', views.image_preview, name='image_preview'),
    path('items/<int:item_id>/quick-create-label/', views.quick_create_label, name='quick_create_label'),
    path('labels/create/', views.create_label, name='create_label'),
    path('labels/<int:label_id>/delete/', views.delete_label, name='delete_label'),
    path('items/<int:item_id>/add-label/', views.add_label_to_item, name='add_label_to_item'),
    path('items/<int:item_id>/remove-label/<int:label_id>/', views.remove_label_from_item, name='remove_label_from_item'),
    path('items/search/', views.search_items, name='search_items'),
    path('items/<int:item_id>/label-section/', views.get_label_section, name='get_label_section'),
    path('items/<int:item_id>/refresh-analysis/', views.refresh_ai_analysis, name='refresh_ai_analysis'),
    path('attachments/<int:attachment_id>/refresh-ai/', views.refresh_attachment_ai, name='refresh_attachment_ai'),
    path('attachments/<int:attachment_id>/generate-description/', views.generate_image_description, name='generate_image_description'),
]
