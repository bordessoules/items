from django.core.management.base import BaseCommand
from inventory.models import Item
from inventory.services.text import TextService
import time
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Update items aggregated descriptions using Mistral model'

    def add_arguments(self, parser):
        parser.add_argument(
            'item_id',
            nargs='?', 
            type=int,
            help='Process specific item by ID'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Update even if description exists'
        )
        parser.add_argument(
            '--prompt',
            type=str,
            help='Override default prompt'
        )

    def handle(self, *args, **options):
        text_service = TextService()

        try:
            # Filter items based on provided ID
            if options['item_id']:
                items = Item.objects.filter(id=options['item_id'])
                if not items.exists():
                    logger.error(f"No item found with ID {options['item_id']}")
                    return
            else:
                items = Item.objects.all()

            logger.info(f"Processing {items.count()} items")

            for item in items:
                if not options['force'] and item.ai_aggregated_description:
                    logger.info(f"Skipping item {item.id} - description exists")
                    continue

                # Get all AI descriptions from item's attachments
                descriptions = []
                for attachment in item.attachments.all():
                    for ai_desc in attachment.attachment_ai_descriptions.all():
                        if ai_desc.response:
                            descriptions.append(ai_desc.response)

                if not descriptions:
                    logger.warning(f"No AI descriptions found for item {item.id}")
                    continue

                # Time the API call
                start_time = time.time()
                summary = text_service.query_text(
                    "\n".join(descriptions),
                    custom_prompt=options.get('prompt')
                )
                
                if summary:
                    item.ai_aggregated_description = summary
                    item.save()
                    elapsed_time = time.time() - start_time
                    logger.info(
                        f"Updated item {item.id} with new summary (took {elapsed_time:.2f}s)"
                    )
                    
                    # Sleep with buffer if needed
                    if elapsed_time < 1.1:
                        time.sleep(1.1 - elapsed_time)
                else:
                    logger.error(f"Failed to generate summary for item {item.id}")

        except Exception as e:
            logger.error(f"Error: {str(e)}")
