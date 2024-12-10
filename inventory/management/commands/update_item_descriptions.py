from django.core.management.base import BaseCommand
from inventory.models import Item
from inventory.services.text import TextService

class Command(BaseCommand):
    help = 'Update items aggregated descriptions using Mistral Nemo'

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
                    self.stdout.write(self.style.ERROR(f"No item found with ID {options['item_id']}"))
                    return
            else:
                items = Item.objects.all()

            self.stdout.write(f"Processing {items.count()} items")

            for item in items:
                if not options['force'] and item.ai_aggregated_description:
                    self.stdout.write(f"Skipping item {item.id} - description exists")
                    continue

                # Get all AI descriptions from item's attachments
                descriptions = []
                for attachment in item.attachments.all():
                    for ai_desc in attachment.attachment_ai_descriptions.all():
                        if ai_desc.response:
                            descriptions.append(ai_desc.response)

                if not descriptions:
                    self.stdout.write(f"No AI descriptions found for item {item.id}")
                    continue

                # Get AI summary using service
                summary = text_service.query_text(
                    "\n".join(descriptions),
                    custom_prompt=options.get('prompt')
                )
                
                if summary:
                    item.ai_aggregated_description = summary
                    item.save()
                    self.stdout.write(self.style.SUCCESS(
                        f"Updated item {item.id} with new summary"
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f"Failed to generate summary for item {item.id}"
                    ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
