from django.core.management.base import BaseCommand
from inventory.models import Attachment, AIImgdescription
from django.core.exceptions import ObjectDoesNotExist
from pathlib import Path
import requests
import base64
import json

class LLaVAClient:
    def __init__(self, base_url: str = "http://192.168.1.112:1234"):
        self.base_url = base_url.rstrip('/')
        self.chat_endpoint = f"{self.base_url}/v1/chat/completions"
    
    def encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def chat(self, text: str, image_path: str) -> str:
        content = [
            {"type": "text", "text": text},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{self.encode_image(image_path)}"
                }
            }
        ]
        
        payload = {
            "model": "llava-v1.5-7b@q4_k_m",
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        try:
            response = requests.post(
                self.chat_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            return f"Error: {str(e)}"

class Command(BaseCommand):
    help = 'Generate AI descriptions for attachments using LLaVA model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--server',
            default="http://192.168.1.112:1234",
            help='LLaVA server URL'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate descriptions even if they already exist'
        )

    def handle(self, *args, **options):
        client = LLaVAClient(base_url=options['server'])
        prompt = "Describe this object in detail. List any visible text, barcodes, or QR codes. Focus only on the main object, ignore background and people."

        try:
            attachments = Attachment.objects.all()
            self.stdout.write(f"Processing {attachments.count()} attachments")

            for attachment in attachments:
                if not options['force'] and attachment.AIdescription.exists():
                    self.stdout.write(f"Skipping {attachment.filename} - description exists")
                    continue

                self.stdout.write(f"Processing {attachment.filename}")
                
                if not attachment.file:
                    self.stdout.write(self.style.WARNING(f"No file found for {attachment.filename}"))
                    continue

                try:
                    file_path = attachment.file.path
                    response = client.chat(prompt, file_path)
                    
                    if response.startswith('Error:'):
                        self.stdout.write(self.style.ERROR(f"Failed to process {attachment.filename}: {response}"))
                        continue

                    # Create or update AI description
                    AIImgdescription.objects.update_or_create(
                        attachment=attachment,
                        defaults={
                            'response': response,
                            'payload': prompt
                        }
                    )
                    
                    self.stdout.write(self.style.SUCCESS(f"Generated description for {attachment.filename}"))
                    self.stdout.write(response)
                    self.stdout.write("-" * 40)

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"Error processing {attachment.filename}: {str(e)}")
                    )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Command failed: {str(e)}")
            )
