# DEV ONLY: python manage.py create_friend_chat <user_uuid> <user_uuid>
from django.core.management.base import BaseCommand

from chat.models import Conversation, Participant


class Command(BaseCommand):
    help = "Create a friend chat between two users (for testing)"

    def add_arguments(self, parser):
        parser.add_argument("user_a")
        parser.add_argument("user_b")

    def handle(self, *args, **options):
        conv = Conversation.objects.create(type=Conversation.Type.FRIEND)
        Participant.objects.create(conversation=conv, user_id=options["user_a"])
        Participant.objects.create(conversation=conv, user_id=options["user_b"])
        self.stdout.write(self.style.SUCCESS(f"Friend chat created: {conv.id}"))
