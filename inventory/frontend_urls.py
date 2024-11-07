# inventory/frontend_urls.py (Frontend URLs)
"""
Frontend URL configuration for the inventory application.
Contains all HTML view URLs.
"""

from django.urls import path
from . import views

# Note: no app_name here as it's defined in main urls.py
urlpatterns = [
    # Main list views
    path('emails/', views.EmailListView.as_view(), name='email_list'),
    path('items/', views.ItemListView.as_view(), name='item_list'),
    path('attachments/', views.AttachmentListView.as_view(), name='attachment_list'),
    path('labels/', views.LabelListView.as_view(), name='label_list'),
    path('items/<int:item_id>/quick-create-label/', views.quick_create_label, name='quick_create_label'),
    path('labels/create/', views.create_label, name='create_label'),
    path('labels/<int:label_id>/delete/', views.delete_label, name='delete_label'),
    
    # Detail views
    path('emails/<int:pk>/', views.EmailDetailView.as_view(), name='email_detail'),
    path('items/<int:pk>/', views.ItemDetailView.as_view(), name='item_detail'),
    
    # HTMX endpoints
    path('items/<int:item_id>/add-label/', 
         views.add_label_to_item, name='add_label_to_item'),
    path('items/<int:item_id>/remove-label/<int:label_id>/', 
         views.remove_label_from_item, name='remove_label_from_item'),
    path('attachments/<int:attachment_id>/preview/', 
         views.image_preview, name='image_preview'),
    path('items/search/', 
         views.search_items, name='search_items'),
     path('items/<int:item_id>/label-section/', 
          views.get_label_section, name='get_label_section'),
     ]