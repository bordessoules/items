from django.core.management.base import BaseCommand
from inventory.models import Item, Attachment, AIImgdescription
from django.core.exceptions import ObjectDoesNotExist


class Command(BaseCommand):
    help = 'Test AI description generation from pictures.'
    
    def handle(self, *args, **options):
        try:
            # Get all attachments
            try:
                attachments = Attachment.objects.all()
            except ObjectDoesNotExist:
                self.stdout.write(
                    self.style.ERROR('Error: No attachments found in database')
                )
                return

            # Vision AI parameters
            model = "pixtral-12b-2409"
            prompt = "quel est l'objet photographié ? pense à bien lister tout le texte et tous les codes-barres que tu vois. Pas de bla-bla. Seul l'objet m'intéresse, pas la personne qui le tient ni l'arrière-plan. "

            for attachment in attachments:
                if attachment.AIdescription.exists():
                    self.stdout.write('Checking' + attachment.name)
                    continue
                # Call vision AI with error handling
                try:
                    response = attachment.query_vision_ai(model, prompt)
                    if response:
                        self.stdout.write(self.style.SUCCESS('Vision AI Response:'))
                        self.stdout.write(str(response))
                    else:
                        self.stdout.write(
                            self.style.WARNING('No response received from Vision AI')
                        )
                except Exception as vision_error:
                    self.stdout.write(
                        self.style.ERROR(f'Error during Vision AI processing: {str(vision_error)}')
                    )

        except Exception as e:
            self.stdout.write(
            self.style.ERROR(f'Unexpected error occurred: {str(e)}')
            )