from django.db import models
from django.core.exceptions import ValidationError
from inventory.services.vision import handle_vision_query
import os
import logging

class Item(models.Model):
    """Core inventory item model."""
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    labels = models.ManyToManyField('Label', related_name='items')
    ai_aggregated_description = models.TextField(
        null=True,
        blank=True,
        help_text="Aggregated AI descriptions from all attachments"
    )    
    def clean(self):
        # Only run this validation if the item already exists (has an ID)
        if self.id and not self.qr_codes.exists():
            raise ValidationError("An item must have at least one QR code.")

    def delete(self, *args, **kwargs):
        # Prevent deletion if this would leave item without QR codes
        if self.qr_codes.count() <= 1:
            raise ValidationError("Cannot delete the last QR code from an item.")
        super().delete(*args, **kwargs)

    def query_vision_ai(self, model_name, prompt):
            return handle_vision_query(self, model_name, prompt)
    
    def __str__(self):
        return f"Item {self.id}: {self.description}"

class QRCode(models.Model):
    """QR code associated with an item."""
    item = models.ForeignKey(Item, related_name='qr_codes', on_delete=models.CASCADE)
    code = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['code'], name='unique_qr_code')
        ]

    def __str__(self):
        return f"QR {self.code} for {self.item}"

class AIdescription(models.Model):
    """AI-generated description for an item."""
    item = models.ForeignKey(Item, related_name='item_ai_descriptions', on_delete=models.CASCADE)
    response = models.TextField(
        null=True,  # Allow null initially
        blank=True,  # Allow blank in forms
        default=""   # Provide empty string default
    )
    payload = models.CharField(
        max_length=4096,
        null=True,  # Allow null initially
        blank=True,  # Allow blank in forms
        default=""   # Provide empty string default
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Response : {self.response} payload :{self.payload} for {self.item}"
    

class Label(models.Model):
    """Label that can be applied to multiple items."""
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Email(models.Model):
    """Email records associated with items."""
    item = models.ForeignKey(
        Item, 
        related_name='emails', 
        on_delete=models.CASCADE,
        null=True,  # Allow emails without items
        blank=True
    )
    email_uid = models.CharField(
        max_length=255, 
        unique=True,
         null=True,  # Allow null initially
        blank=True,
        help_text="Composite unique identifier: sender_email:folder:imap_uid"
    )
    subject = models.CharField(max_length=255)
    sender = models.EmailField()
    recipients = models.JSONField(help_text="List of email addresses")
    body = models.TextField()
    thread_id = models.CharField(max_length=100, null=True, blank=True)
    sent_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['sender']),
            models.Index(fields=['sent_at']),
            models.Index(fields=['thread_id']),
            models.Index(fields=['email_uid']),
        ]

    def __str__(self):
        return f"Email: {self.subject}"
    @staticmethod
    def generate_uid(sender_email, folder, imap_uid):
        """Generate a unique composite identifier"""
        clean_email = sender_email.replace('@', 'at')  # Remove @ from email
        return f"{clean_email}_{folder}_{imap_uid}"

class Attachment(models.Model):
    """
    File attachments that can be associated with items and optionally emails.
    Can be added manually or come from emails.
    """
    item = models.ForeignKey(
        Item, 
        related_name='attachments', 
        on_delete=models.CASCADE,
        null=True,  
        blank=True 
    )
    email = models.ForeignKey(
        Email, 
        related_name='attachments', 
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    file = models.FileField(
        upload_to='attachments',
        null=True,  # Allow null files
        blank=True  # Make field optional
    )
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField(
        help_text="File size in bytes",
        default=0  # Add default value
    )
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(
        max_length=20,
        choices=[
            ('EMAIL', 'From Email'),
            ('UPLOAD', 'Manual Upload'),
            ('API', 'API Upload'),
        ],
        default='UPLOAD',
        help_text="Source of the attachment"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['source']),
        ]
    @property
    def is_image(self):
        return self.content_type.startswith('image/') if self.content_type else False
    def __str__(self):
        return f"Response : {self.response} payload :{self.payload} "
    def query_vision_ai(self, model_name, prompt):
        response_tuple = handle_vision_query(self, model_name, prompt)
        response, _ = response_tuple
        self.attachment_ai_descriptions.create(response=response, payload={"model":model_name, "promt":prompt})
        #self.AIImgdescription.create(response=response, payload={"model":model_name, "promt":prompt})
        return response
    
    @property
    def has_valid_file(self):
        return bool(self.file and self.file.name)
    
class AIImgdescription(models.Model):
    """AI-generated description for an item."""
    attachment = models.ForeignKey(Attachment, related_name='attachment_ai_descriptions', on_delete=models.CASCADE)
    response = models.TextField(
        null=True,  # Allow null initially
        blank=True,  # Allow blank in forms
        default=""   # Provide empty string default
    )
    payload = models.CharField(
        max_length=4096,
        null=True,  # Allow null initially
        blank=True,  # Allow blank in forms
        default=""   # Provide empty string default
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        #return f"{self.filename} ({self.get_source_display()})"
        return f"AI Description for {self.attachment.filename}"


    #def save(self, *args, **kwargs):
    #    if not self.filename and self.file:
    #        self.filename = os.path.basename(self.file.name)
    #    if not self.size and self.file:
    #        self.size = self.file.size
    #    if self.email and not self.source:
    #        self.source = 'EMAIL'
    #    super().save(*args, **kwargs)

    @property
    def is_pdf(self):
        return self.content_type == 'application/pdf'

    @property
    def has_valid_file(self):
        return bool(self.file and self.file.name)

class ListingCategory(models.Model):
    """Categories for LeBonCoin listings"""
    name = models.CharField(max_length=100)    
    class Meta:
        verbose_name_plural = "Listing categories"
    
    def __str__(self):
        return f"{self.parent.name} > {self.name}" if self.parent else self.name

class ListingLBC(models.Model):
    """Listing on the LeBonCoin website."""
    CATEGORY_CHOICES = [
        ('ordinateurs', 'Ordinateurs'),
        ('accessoires_informatique', 'Accessoires informatique'),
        ('tablettes_liseuses', 'Tablettes & Liseuses'),
        ('photo_audio_video', 'Photo, audio & vidéo'),
        ('telephones_objets_connectes', 'Téléphones & Objets connectés'),
        ('accessoires_telephone', 'Accessoires téléphone & Objets connectés'),
    ]

    item = models.ForeignKey(Item, related_name='listings_lbc', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    price = models.IntegerField()
    description = models.TextField()
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='ordinateurs'
    )
    created_at = models.DateTimeField(auto_now_add=True)