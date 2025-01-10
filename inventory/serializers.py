from rest_framework import serializers
from .models import Item, ListingLBC, QRCode, Label, Email, Attachment

class AttachmentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Attachment
        fields = ['id', 'filename', 'content_type', 'size', 'created_at', 
                 'is_image', 'is_pdf', 'download_url']
        read_only_fields = ['size', 'content_type', 'is_image', 'is_pdf']

    def get_download_url(self, obj):
        request = self.context.get('request')
        if request and obj.file:
            return request.build_absolute_uri(obj.file.url)
        return None

class EmailSerializer(serializers.ModelSerializer):
    attachments = AttachmentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Email
        fields = ['id', 'subject', 'sender', 'recipients', 'body', 
                 'thread_id', 'sent_at', 'created_at', 'attachments']

class QRCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = QRCode
        fields = ['id', 'code', 'created_at']

class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['id', 'name', 'created_at']

class ItemSerializer(serializers.ModelSerializer):
    qr_codes = QRCodeSerializer(many=True, read_only=True)
    labels = LabelSerializer(many=True, read_only=True)
    emails = EmailSerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    # Field for creating/updating QR codes
    new_qr_codes = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Item
        fields = [
            'id', 'description', 'created_at', 'updated_at',
            'qr_codes', 'labels', 'emails', 'attachments', 'new_qr_codes'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        # When creating a new item
        if not self.instance and not self.initial_data.get('new_qr_codes'):
            raise serializers.ValidationError(
                "A new item must be created with at least one QR code."
            )
        return data

    def create(self, validated_data):
        new_qr_codes = validated_data.pop('new_qr_codes', [])
        item = Item.objects.create(**validated_data)
        
        # Add QR codes
        existing_codes = []
        for code in new_qr_codes:
            if QRCode.objects.filter(code=code).exists():
                existing_codes.append(code)
                continue
            try:
                QRCode.objects.create(item=item, code=code)
            except Exception as e:
                print(f"Error adding QR code {code}: {e}")
        
        if existing_codes:
            raise serializers.ValidationError(
                f"QR codes already in use: {', '.join(existing_codes)}"
            )
        
        return item

    def update(self, instance, validated_data):
        new_qr_codes = validated_data.pop('new_qr_codes', [])
        
        # Update basic fields
        instance = super().update(instance, validated_data)
        
        # Add new QR codes
        existing_codes = []
        for code in new_qr_codes:
            if QRCode.objects.filter(code=code).exists():
                existing_codes.append(code)
                continue
            try:
                QRCode.objects.create(item=instance, code=code)
            except Exception as e:
                print(f"Error adding QR code {code}: {e}")
        
        if existing_codes:
            raise serializers.ValidationError(
                f"QR codes already in use: {', '.join(existing_codes)}"
            )
        
        return instance

class ListingLBCSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingLBC
        fields = ['id', 'item', 'title', 'price', 'description', 'category']
