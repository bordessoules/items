from django.core.management.base import BaseCommand
from inventory.models import Item, Attachment, AIImgdescription
from django.core.exceptions import ObjectDoesNotExist


class Command(BaseCommand):
    help = 'Test AI description generation from pictures.'
    
    def handle(self, *args, **options):
        try:
            # Get attachment with error handling
            attachment_id = 9
            try:
                att = Attachment.objects.all()
            except ObjectDoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Error: Attachment with ID {attachment_id} not found')
                )
                return

            # Vision AI parameters
            model = "pixtral-12b-2409"
            prompt = "quel est l'objet photographié ? pense à bien lister tout le texte et tous les codes-barres que tu vois. Pas de bla-bla. Seul l'objet m'intéresse, pas la personne qui le tient ni l'arrière-plan. "

            for at in att:
                if at.AIdescription.exists():
                    continue
                # Call vision AI with error handling
                try:
                    response = at.query_vision_ai(model, prompt)
                    if response:
                        self.stdout.write(self.style.SUCCESS('Vision AI Response:'))
                        #self.stdout.write(str(response))
                    else:
                        self.stdout.write(
                            self.style.WARNING('No response received from Vision AI')
                        )
                except Exception as vision_error:
                    self.stdout.write(
                        self.style.ERROR(f'Error during Vision AI processing: {str(vision_error)}')
                    )
                    return

        except Exception as e:
            self.stdout.write(
            self.style.ERROR(f'Unexpected error occurred: {str(e)}')
            )
