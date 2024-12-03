from django.contrib import admin
from .models import Item, QRCode, Label, Email, Attachment, AIImgdescription

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'description', 'created_at', 'updated_at')
    search_fields = ('description',)

@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'item', 'created_at')
    search_fields = ('code',)

@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender', 'sent_at', 'item')
    search_fields = ('subject', 'sender')
    list_filter = ('sent_at',)

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('filename', 'content_type', 'size', 'created_at')
    list_filter = ('content_type',)
    search_fields = ('filename',)

@admin.register(AIImgdescription)
class AIImgdescriptionAdmin(admin.ModelAdmin):
    list_display = ('attachment', 'payload', 'response')