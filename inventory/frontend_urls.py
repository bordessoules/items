from django.urls import path
from .views import EmailListView, EmailDetailView

app_name = 'inventory'

urlpatterns = [
    path('', EmailListView.as_view(), name='email_list'),
    path('email/<int:pk>/', EmailDetailView.as_view(), name='email_detail'),
]