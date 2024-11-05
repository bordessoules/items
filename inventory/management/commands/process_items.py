"""
Django management command to process emails and create/update inventory items based on QR codes.

This command processes emails in two passes:
1. Creates new items from emails with exactly 5-digit QR code subjects
2. Updates existing items from reply emails (re:12345 format)

Each pass also processes additional QR codes found in email bodies (geek12345 format)
and handles email attachments.
"""

from typing import List, Tuple, Optional
import re
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import QuerySet
from inventory.models import Email, Item, QRCode, Attachment

# Configure logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """Django command to process emails and create/update inventory items."""
    
    help = 'Process emails in two passes: first new items, then reply updates'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dry_run: bool = False
        self.verbose: bool = False
        self.stats = {
            'total_processed': 0,
            'items_created': 0,
            'emails_skipped': 0,
            'errors': 0
        }

    def add_arguments(self, parser) -> None:
        """Add command line arguments."""
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making changes to database'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed processing information'
        )

    def handle(self, *args, **options) -> None:
        """Main command handler."""
        self.dry_run = options['dry_run']
        self.verbose = options['verbose']

        try:
            self.stdout.write(self.style.SUCCESS("\nPASS 1: Processing primary emails"))
            self.process_primary_emails()

            self.stdout.write(self.style.SUCCESS("\nPASS 2: Processing reply emails"))
            self.process_reply_emails()

            self.print_final_stats()
        except Exception as e:
            logger.error(f"Critical error in command execution: {str(e)}")
            self.stdout.write(self.style.ERROR(f"Command failed: {str(e)}"))
            raise

    def clean_text(self, text: Optional[str]) -> str:
        """
        Remove all whitespace and convert to lowercase.
        
        Args:
            text: Input text to clean
            
        Returns:
            Cleaned text with no whitespace and all lowercase
        """
        if not text:
            return ""
        return ''.join(text.lower().split())

    def extract_geek_qr_codes(self, message: Optional[str]) -> List[str]:
        """
        Extract QR codes with 'geek' prefix from message text.
        
        Args:
            message: Email message text to search
            
        Returns:
            List of unique 5-digit QR codes found
        """
        if not message:
            return []
            
        # Clean message but preserve word boundaries
        cleaned_message = ' '.join(message.lower().split())
        
        # Find all 'geek' prefixed 5-digit codes
        matches = re.finditer(r'\bgeek\s*(\d{5})\b', cleaned_message)
        
        # Return unique codes only
        unique_codes = list({match.group(1) for match in matches})
        self.debug_log(f"Found QR codes in message: {unique_codes}")
        return unique_codes

    def is_pure_qr_code(self, subject: Optional[str]) -> bool:
        """
        Check if string is exactly a 5-digit number.
        
        Args:
            subject: Text to check
            
        Returns:
            True if text is exactly 5 digits after cleaning
        """
        if not subject:
            return False
        cleaned = self.clean_text(subject)
        return bool(re.match(r'^\d{5}$', cleaned))

    def is_valid_reply_subject(self, subject: Optional[str]) -> Tuple[bool, str]:
        """
        Check if subject matches reply format and extract QR code.
        
        Args:
            subject: Email subject to check
            
        Returns:
            Tuple of (is_valid, qr_code)
        """
        if not subject:
            return False, ""
        
        cleaned = self.clean_text(subject)
        match = re.match(r'^re:?(\d{5})$', cleaned)
        
        if match:
            code = match.group(1)
            self.debug_log(f"Valid reply format found, code: {code}")
            return True, code
        return False, ""

    def link_attachments_to_item(self, email: Email, item: Item) -> None:
        """
        Link all email attachments to an item.
        
        Args:
            email: Source email containing attachments
            item: Target item to link attachments to
        """
        for attachment in email.attachments.all():
            try:
                attachment.item = item
                attachment.save()
                self.debug_log(f"Linked attachment {attachment.filename} to item {item.id}")
            except Exception as e:
                logger.error(f"Error linking attachment {attachment.id}: {str(e)}")
                self.stats['errors'] += 1

    def add_qr_codes_to_item(self, item: Item, qr_codes: List[str]) -> None:
        """
        Add multiple QR codes to an item, skipping existing ones.
        
        Args:
            item: Target item to add QR codes to
            qr_codes: List of QR codes to add
        """
        for code in qr_codes:
            try:
                if not QRCode.objects.filter(code=code).exists():
                    QRCode.objects.create(item=item, code=code)
                    self.debug_log(f"Added QR code {code} to item {item.id}")
                else:
                    self.debug_log(f"Skipped existing QR code {code}")
            except Exception as e:
                logger.error(f"Error adding QR code {code}: {str(e)}")
                self.stats['errors'] += 1

    def process_primary_emails(self) -> None:
        """Process emails where subject is exactly a QR code to create new items."""
        unprocessed = Email.objects.filter(item__isnull=True).order_by('sent_at')
        total = unprocessed.count()
        
        self.stdout.write(f"Found {total} unprocessed emails")
        
        for email in unprocessed:
            self.debug_log(f"\nChecking: {email.email_uid}")
            self.debug_log(f"Subject: {email.subject}")

            try:
                if not self.is_pure_qr_code(email.subject):
                    self.debug_log("Skipping (not exact QR code)")
                    self.stats['emails_skipped'] += 1
                    continue

                qr_code = self.clean_text(email.subject)
                
                if QRCode.objects.filter(code=qr_code).exists():
                    self.debug_log(f"Skipping (QR {qr_code} exists)")
                    self.stats['emails_skipped'] += 1
                    continue

                additional_qr_codes = self.extract_geek_qr_codes(email.body)

                if not self.dry_run:
                    try:
                        with transaction.atomic():
                            # Create new item with initial QR code
                            item = Item.objects.create(description=f"Item {qr_code}")
                            QRCode.objects.create(item=item, code=qr_code)
                            
                            # Add additional QR codes from message
                            self.add_qr_codes_to_item(item, additional_qr_codes)
                            
                            # Link email and attachments
                            email.item = item
                            email.save()
                            self.link_attachments_to_item(email, item)
                            
                            self.debug_log(f"Created item {item.id}")
                            self.stats['items_created'] += 1
                            self.stats['total_processed'] += 1
                    except Exception as e:
                        logger.error(f"Error processing email {email.email_uid}: {str(e)}")
                        self.stats['errors'] += 1
                        self.stats['emails_skipped'] += 1
                else:
                    self.debug_log("Would create item (dry run)")
                    self.stats['items_created'] += 1
                    self.stats['total_processed'] += 1
                    
            except Exception as e:
                logger.error(f"Unexpected error processing email {email.email_uid}: {str(e)}")
                self.stats['errors'] += 1
                self.stats['emails_skipped'] += 1

    def process_reply_emails(self) -> None:
        """Process reply emails to update existing items."""
        remaining = Email.objects.filter(item__isnull=True).order_by('sent_at')
        total = remaining.count()
        
        self.stdout.write(f"Found {total} remaining emails")

        for email in remaining:
            self.debug_log(f"\nChecking: {email.email_uid}")
            self.debug_log(f"Subject: {email.subject}")

            try:
                is_reply, qr_code = self.is_valid_reply_subject(email.subject)
                if not is_reply:
                    self.debug_log("Skipping (not a valid reply format)")
                    self.stats['emails_skipped'] += 1
                    continue

                try:
                    qr = QRCode.objects.select_related('item').get(code=qr_code)
                    item = qr.item

                    if not self.dry_run:
                        with transaction.atomic():
                            # Add any new QR codes from message
                            additional_qr_codes = self.extract_geek_qr_codes(email.body)
                            self.add_qr_codes_to_item(item, additional_qr_codes)
                            
                            # Link email and attachments
                            email.item = item
                            email.save()
                            self.link_attachments_to_item(email, item)
                            
                            self.debug_log(f"Updated item {item.id}")
                            self.stats['total_processed'] += 1
                except QRCode.DoesNotExist:
                    self.debug_log(f"Skipping (QR {qr_code} not found)")
                    self.stats['emails_skipped'] += 1
                    
            except Exception as e:
                logger.error(f"Error processing reply email {email.email_uid}: {str(e)}")
                self.stats['errors'] += 1
                self.stats['emails_skipped'] += 1

    def print_final_stats(self) -> None:
        """Print final processing statistics."""
        self.stdout.write("\nProcessing Complete:")
        self.stdout.write(f"  Total Processed: {self.stats['total_processed']}")
        self.stdout.write(f"  Items Created: {self.stats['items_created']}")
        self.stdout.write(f"  Emails Skipped: {self.stats['emails_skipped']}")
        self.stdout.write(f"  Errors: {self.stats['errors']}")

    def debug_log(self, message: str) -> None:
        """Log debug message if verbose mode is enabled."""
        if self.verbose:
            self.stdout.write(f"DEBUG: {message}")
        logger.debug(message)