from django.core.management.base import BaseCommand
from inventory.models import Item, AIdescription
import requests
import json
from typing import Optional, Dict, Any

DEFAULT_PROMPT = """You are analyzing a collection of AI-generated descriptions of images related to a single inventory item. 
These descriptions were created by a vision model (LLaVA) that examined multiple photos of the item.

Your task:
1. Synthesize these descriptions into a coherent summary
2. Extract and list all identified:
   - QR codes or barcodes
   - Text or labels visible on the item
   - Physical characteristics
3. Note any discrepancies between different image descriptions
4. Highlight key features that appear consistently across descriptions

Format your response as:
SUMMARY: Brief overview of the item
IDENTIFIERS: Any codes or serial numbers
PHYSICAL DETAILS: Size, color, condition, materials
NOTABLE FEATURES: Distinctive characteristics
CONSISTENCY CHECK: Note any variations between descriptions

Focus on factual information and maintain a technical, inventory-appropriate tone."""

class QwenClient:
    def __init__(self, base_url: str = "http://host.docker.internal:1234"):
        self.base_url = base_url.rstrip('/')
        self.chat_endpoint = f"{self.base_url}/v1/chat/completions"
        self.default_prompt = DEFAULT_PROMPT    
    def analyze(self, 
                text: str, 
                prompt: str, 
                temperature: float = 0.7, 
                max_tokens: int = 500) -> str:
        payload = {
            "model": "Qwen2.5-3B-Instruct-Q8_0",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
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
    help = 'Process aggregated descriptions using Qwen model for additional analysis'

    def add_arguments(self, parser):
        parser.add_argument(
            'item_id',
            nargs='?',
            type=int,
            help='Process specific item by ID'
        )
        parser.add_argument(
            '--server',
            default="http://host.docker.internal:1234",
            help='Qwen server URL'
        )
        parser.add_argument(
            '--prompt',
            default=DEFAULT_PROMPT,
            help='Custom prompt for the analysis'
        )
        parser.add_argument(
            '--temperature',
            type=float,
            default=0.7,
            help='Temperature for response generation (default: 0.7)'
        )
        parser.add_argument(
            '--max-tokens',
            type=int,
            default=500,
            help='Maximum tokens in response (default: 500)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate analysis even if it exists'
        )

    def handle(self, *args, **options):
        client = QwenClient(base_url=options['server'])

        try:
            # Filter items based on provided ID
            if options['item_id']:
                items = Item.objects.filter(id=options['item_id'])
                if not items.exists():
                    self.stdout.write(self.style.ERROR(f"No item found with ID {options['item_id']}"))
                    return
            else:
                items = Item.objects.exclude(ai_aggregated_description__isnull=True)

            self.stdout.write(f"Processing {items.count()} items")

            for item in items:
                if not options['force'] and item.AIdescription.exists():
                    self.stdout.write(f"Skipping item {item.id} - analysis exists")
                    continue

                if not item.ai_aggregated_description:
                    self.stdout.write(f"Skipping item {item.id} - no aggregated description")
                    continue

                self.stdout.write(f"Processing item {item.id}")
                
                response = client.analyze(
                    text=item.ai_aggregated_description,
                    prompt=options['prompt'],
                    temperature=options['temperature'],
                    max_tokens=options['max_tokens']
                )
                
                if response.startswith('Error:'):
                    self.stdout.write(self.style.ERROR(f"Failed to process item {item.id}: {response}"))
                    continue

                # Store analysis metadata
                analysis_metadata = {
                    "model": "Qwen2.5-3B-Instruct-Q8_0",
                    "prompt": options['prompt'],
                    "temperature": options['temperature'],
                    "max_tokens": options['max_tokens'],
                    "source_text": item.ai_aggregated_description
                }

                # Create or update AI description
                AIdescription.objects.update_or_create(
                    item=item,
                    defaults={
                        'response': response,
                        'payload': analysis_metadata
                    }
                )
                
                self.stdout.write(self.style.SUCCESS(f"Generated analysis for item {item.id}"))
                self.stdout.write("Analysis:")
                self.stdout.write(response)
                self.stdout.write("-" * 40)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Command failed: {str(e)}"))
