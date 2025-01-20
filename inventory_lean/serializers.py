from rest_framework import serializers
from .models import Item, Label, QRCode, Attachment

class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['id', 'name']

class QRCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = QRCode
        fields = ['id', 'code']

class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ['id', 'file', 'filename', 'content_type']

class ItemSerializer(serializers.ModelSerializer):
    labels = LabelSerializer(many=True, read_only=True)
    qr_codes = QRCodeSerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Item
        fields = ['id', 'description', 'created_at', 'labels', 'qr_codes', 'attachments']
