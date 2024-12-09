from django.core.management.base import BaseCommand
from inventory.models import Item, AIImgdescription
from django.db.models import F

class Command(BaseCommand):
    help = 'Aggregate attachment AI descriptions into item text field'

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
            help='Regenerate aggregated descriptions even if they exist'
        )

    def handle(self, *args, **options):
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
                # Get all AI descriptions from item's attachments
                ai_descriptions = AIImgdescription.objects.filter(
                    attachment__item=item
                ).values_list('response', flat=True)

                if not ai_descriptions:
                    self.stdout.write(f"No AI descriptions found for item {item.id}")
                    continue

                # Aggregate descriptions into a single text
                aggregated_text = "\n\n".join([
                    f"Attachment description:\n{desc}" 
                    for desc in ai_descriptions if desc
                ])

                # Update item's text field
                item.ai_aggregated_description = aggregated_text
                item.save()

                self.stdout.write(self.style.SUCCESS(
                    f"Updated item {item.id} with {len(ai_descriptions)} descriptions"
                ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Command failed: {str(e)}"))
