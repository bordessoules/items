from django.db import models
from pathlib import Path

def attachment_path(instance, filename):
    # Organize files: attachments/item_id/type/filename
    return f'attachments/{instance.item.id}/{instance.get_type()}/{filename}'

class Item(models.Model):
    description = models.TextField(blank=True)
    ai_generated_description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    labels = models.ManyToManyField('Label', related_name='items')

    class Meta:
        ordering = ['-created_at']

    def get_images(self):
        return self.attachments.filter(content_type__startswith='image/')

    def generate_description(self):
        descriptions = [a.ai_description for a in self.get_images() if a.ai_description]
        if descriptions:
            from .services.text import analyze_descriptions
            self.ai_generated_description = analyze_descriptions(descriptions)
            self.save()

class Attachment(models.Model):
    item = models.ForeignKey(Item, related_name='attachments', on_delete=models.CASCADE)
    file = models.FileField(upload_to=attachment_path)
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    ai_description = models.TextField(blank=True, null=True)
    
    def get_type(self):
        if self.content_type.startswith('image/'):
            return 'images'
        return 'documents'

    @property
    def is_image(self):
        return self.content_type.startswith('image/')

class Email(models.Model):
    item = models.ForeignKey(Item, related_name='emails', on_delete=models.CASCADE)
    subject = models.CharField(max_length=255)
    from_address = models.EmailField()
    body = models.TextField()
    received_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

class QRCode(models.Model):
    item = models.ForeignKey(Item, related_name='qr_codes', on_delete=models.CASCADE)
    code = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Label(models.Model):
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
