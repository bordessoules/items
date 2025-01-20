import re
from django.core.management.base import BaseCommand
from ...models import Item, QRCode, Email, Attachment
from pathlib import Path

class Command(BaseCommand):
    help = 'Process emails to create items from QR codes'

    def handle(self, *args, **options):
        for email in Email.objects.filter(processed=False):
            qr_match = re.search(r'\d{5}', email.subject)
            if qr_match:
                code = qr_match.group()
                item = Item.objects.create()
                QRCode.objects.create(item=item, code=code)
                
                # Save email
                Email.objects.create(
                    item=item,
                    subject=email.subject,
                    from_address=email.from_address,
                    body=email.body
                )

                # Process attachments
                for attachment in email.get_attachments():
                    Attachment.objects.create(
                        item=item,
                        file=attachment.file,
                        filename=attachment.filename,
                        content_type=attachment.content_type
                    )
                
                email.processed = True
                email.save()
