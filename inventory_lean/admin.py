from django.contrib import admin
from .models import Item, Label, QRCode, Attachment

admin.site.register(Item)
admin.site.register(Label)
admin.site.register(QRCode)
admin.site.register(Attachment)
