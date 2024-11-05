import os
import email
import imaplib
import time
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import datetime, timedelta
import concurrent.futures
import socket
import ssl
from email.header import decode_header
from email.utils import parsedate_to_datetime
import re
import threading
from dotenv import load_dotenv
from inventory.models import Email, Attachment

class Command(BaseCommand):
    help = 'Fetch emails from IMAP server and store them with attachments'

    def __init__(self):
        super().__init__()
        self.thread_local = threading.local()
        self.attachment_count = 0
        self.attachment_errors = 0

    def add_arguments(self, parser):
        parser.add_argument('--threads', type=int, default=8)  
        parser.add_argument('--batch-size', type=int, default=100)  

    def get_connection(self):
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                if hasattr(self.thread_local, 'mail'):
                    try:
                        # Test the connection
                        self.thread_local.mail.noop()
                        return self.thread_local.mail
                    except:
                        # Connection is dead, remove it
                        self.thread_local.mail = None
                
                # Create new connection
                mail = imaplib.IMAP4_SSL(os.getenv('EMAIL_HOST'))
                mail.login(os.getenv('EMAIL_USER'), os.getenv('EMAIL_PASSWORD'))
                mail.select(os.getenv('EMAIL_FOLDER'))
                self.thread_local.mail = mail
                return mail
                
            except (socket.error, ssl.SSLError, imaplib.IMAP4.error) as e:
                if attempt == max_retries - 1:  # Last attempt
                    raise
                self.stdout.write(self.style.WARNING(f'Connection attempt {attempt + 1} failed: {str(e)}. Retrying in {retry_delay} seconds...'))
                time.sleep(retry_delay)

    def decode_email_header(self, header):
        if not header:
            return ''
        decoded_parts = []
        for decoded_string, charset in decode_header(header):
            if isinstance(decoded_string, bytes):
                try:
                    if charset:
                        decoded_parts.append(decoded_string.decode(charset))
                    else:
                        decoded_parts.append(decoded_string.decode())
                except (UnicodeDecodeError, LookupError):
                    decoded_parts.append(decoded_string.decode('utf-8', 'ignore'))
            else:
                decoded_parts.append(decoded_string)
        return ' '.join(decoded_parts)

    def decode_email_part(self, part):
        content = part.get_payload(decode=True)
        if content is None:
            return ''
        
        charset = part.get_content_charset() or 'utf-8'
        try:
            return content.decode(charset, 'ignore')
        except (UnicodeDecodeError, LookupError):
            return content.decode('utf-8', 'ignore')

    def parse_date(self, date_str):
        try:
            return parsedate_to_datetime(date_str)
        except (TypeError, ValueError):
            return timezone.now()

    def parse_uid(self, response):
        try:
            uid = re.search(r'UID (\d+)', response.decode('utf-8')).group(1)
            return uid
        except (AttributeError, IndexError):
            return None

    def save_attachment(self, part, email_obj):
        filename = part.get_filename()
        if filename:
            try:
                content = part.get_payload(decode=True)
                if content is None:
                    self.stdout.write(self.style.WARNING(f"Empty content for attachment {filename}"))
                    return

                unique_filename = f"{email_obj.email_uid}_{filename}"
                
                content_size = len(content)
                self.stdout.write(f"Processing attachment: {filename} ({content_size} bytes)")
                
                media_root = os.path.join(os.getcwd(), 'media')
                if not os.path.exists(media_root):
                    os.makedirs(media_root)
                    self.stdout.write(f"Created media directory at {media_root}")

                # Create attachment with source explicitly set
                attachment = Attachment.objects.create(
                    email=email_obj,
                    filename=filename,
                    content_type=part.get_content_type(),
                    size=content_size,
                    source='EMAIL'  # Explicitly set the source
                )

                # Then save the file
                attachment.file.save(unique_filename, ContentFile(content), save=True)
                if attachment.file and os.path.exists(attachment.file.path):
                    self.stdout.write(
                        self.style.SUCCESS(f"Saved attachment: {unique_filename} to {attachment.file.path}")
                    )
                    self.attachment_count += 1
                else:
                    self.stdout.write(
                        self.style.ERROR(f"File not found after save: {attachment.file.path}")
                    )

            except Exception as e:
                self.attachment_errors += 1
                self.stdout.write(
                    self.style.ERROR(f"Failed to save attachment {filename}: {str(e)}")
                )

    def process_email(self, email_id):
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                mail = self.get_connection()
                _, msg_data = mail.fetch(email_id, '(RFC822 UID)')
                email_body = msg_data[0][1]
                imap_uid = self.parse_uid(msg_data[0][0])
                
                email_message = email.message_from_bytes(email_body)
                sender = self.decode_email_header(email_message['from'])
                
                sender_email = re.search(r'<(.+?)>', sender)
                if sender_email:
                    sender_email = sender_email.group(1)
                else:
                    sender_email = sender.strip()

                email_uid = f"{sender_email}:{os.getenv('EMAIL_FOLDER')}:{imap_uid}"

                if Email.objects.filter(email_uid=email_uid).exists():
                    return "skipped"

                subject = self.decode_email_header(email_message['subject'])
                recipients = self.decode_email_header(email_message['to'])
                date_str = email_message['date']
                sent_at = self.parse_date(date_str) if date_str else timezone.now()

                email_obj = Email.objects.create(
                    email_uid=email_uid,
                    subject=subject,
                    sender=sender_email,
                    recipients=recipients.split(',') if recipients else [],
                    body='',
                    thread_id=email_message['message-id'],
                    sent_at=sent_at,
                )

                has_attachments = False
                for part in email_message.walk():
                    if part.get_content_maintype() == 'text' and part.get_content_subtype() == 'plain':
                        email_obj.body += self.decode_email_part(part)
                    elif part.get_content_maintype() in ['image', 'application']:
                        has_attachments = True
                        self.save_attachment(part, email_obj)

                email_obj.save()
                
                status_msg = f"Fetched email {email_uid}"
                if has_attachments:
                    status_msg += " (with attachments)"
                self.stdout.write(self.style.SUCCESS(status_msg))
                
                return "processed"
                
            except (socket.error, ssl.SSLError, imaplib.IMAP4.error) as e:
                if attempt == max_retries - 1:  # Last attempt
                    self.stdout.write(self.style.ERROR(f'Error with email {email_id} after {max_retries} attempts: {str(e)}'))
                    return "error"
                self.stdout.write(self.style.WARNING(f'Attempt {attempt + 1} failed for email {email_id}: {str(e)}. Retrying in {retry_delay} seconds...'))
                time.sleep(retry_delay)
                # Force new connection on next attempt
                if hasattr(self.thread_local, 'mail'):
                    self.thread_local.mail = None

    def handle(self, *args, **options):
        load_dotenv()
        required_env = ['EMAIL_HOST', 'EMAIL_USER', 'EMAIL_PASSWORD', 'EMAIL_FOLDER']
        missing_env = [var for var in required_env if not os.getenv(var)]
        if missing_env:
            self.stdout.write(self.style.ERROR(f'Missing environment variables: {", ".join(missing_env)}'))
            return

        try:
            mail = self.get_connection()
            _, messages = mail.search(None, 'ALL')
            email_ids = messages[0].split()
            total_emails = len(email_ids)
            
            existing_count = Email.objects.count()
            existing_attachments = Attachment.objects.count()
            
            self.stdout.write(f'Total emails on server: {total_emails}')
            self.stdout.write(f'Existing emails in database: {existing_count}')
            self.stdout.write(f'Existing attachments in database: {existing_attachments}')
            
            media_path = os.path.join(os.getcwd(), 'media')
            self.stdout.write(f'Media directory path: {media_path}')
            if os.path.exists(media_path):
                media_files = len([f for f in os.listdir(media_path) if os.path.isfile(os.path.join(media_path, f))])
                self.stdout.write(f'Files in media directory: {media_files}')
            else:
                self.stdout.write(self.style.WARNING('Media directory does not exist!'))
            
            thread_count = options['threads']
            batch_size = options['batch_size']
            processed_count = 0
            skipped_count = 0
            error_count = 0
            start_time = time.time()

            self.stdout.write(f'Using {thread_count} threads and batch size of {batch_size}')

            with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count) as executor:
                for i in range(0, total_emails, batch_size):
                    batch = email_ids[i:i + batch_size]
                    batch_start_time = time.time()
                    
                    futures = [executor.submit(self.process_email, email_id) for email_id in batch]
                    
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            result = future.result()
                            if result == "skipped":
                                skipped_count += 1
                            elif result == "processed":
                                processed_count += 1
                            elif result == "error":
                                error_count += 1
                        except Exception as e:
                            error_count += 1
                            self.stdout.write(self.style.ERROR(f'Future error: {str(e)}'))

                    batch_time = time.time() - batch_start_time
                    emails_per_second = len(batch) / batch_time if batch_time > 0 else 0
                    
                    self.stdout.write(
                        f'\nBatch {i//batch_size + 1}/{(total_emails + batch_size - 1)//batch_size}:'
                        f'\n- Time taken: {batch_time:.2f}s'
                        f'\n- Processing speed: {emails_per_second:.2f} emails/second'
                        f'\n- Processed: {processed_count}'
                        f'\n- Skipped (already exists): {skipped_count}'
                        f'\n- Errors: {error_count}'
                        f'\n- Total progress: {((i + len(batch)) / total_emails) * 100:.1f}%'
                    )

                    # Add delay between batches
                    #time.sleep(2)

            total_time = time.time() - start_time
            self.stdout.write(self.style.SUCCESS(
                f'\nFinal Summary:'
                f'\n- Total time: {total_time:.2f}s'
                f'\n- Total processed: {processed_count}'
                f'\n- Total skipped: {skipped_count}'
                f'\n- Total errors: {error_count}'
                f'\n- Attachments processed: {self.attachment_count}'
                f'\n- Attachment errors: {self.attachment_errors}'
                f'\n- Average speed: {(processed_count + skipped_count) / total_time:.2f} emails/second'
                f'\n- Emails in database: {Email.objects.count()}'
                f'\n- Attachments in database: {Attachment.objects.count()}'
            ))

        except (socket.error, ssl.SSLError, imaplib.IMAP4.error) as e:
            self.stdout.write(self.style.ERROR(f'Connection error: {str(e)}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Unexpected error: {str(e)}'))
        finally:
            try:
                if hasattr(self.thread_local, 'mail'):
                    self.thread_local.mail.close()
                    self.thread_local.mail.logout()
            except:
                pass