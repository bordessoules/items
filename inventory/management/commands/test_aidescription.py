from django.core.management.base import BaseCommand
from inventory.models import Item, Attachment, AIImgdescription


class Command(BaseCommand):
    
    def handle(self, *args, **options):
        help = 'Test AI description generation from pictures.'
        # item = Item.objects.get(id=9)
        # print(item)
        # print(item.query_vision_ai("pixtral-12b-2409", "décrit ce que tu vois"))
        at = Attachment.objects.get(id=9)

        # for at in att :
        model = "pixtral-12b-2409"
        prompt = "décrit ce que tu vois"
        response = at.query_vision_ai(model, prompt)
        print(response)