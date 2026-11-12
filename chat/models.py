import uuid

from django.db import models


class Conversation(models.Model):

    class Type(models.TextChoices):
        FRIEND = "friend"
        LOBBY = "lobby"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=10, choices=Type.choices)
    # only set for lobby chats; unique so a retried request returns the same chat
    lobby_id = models.UUIDField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Participant(models.Model):

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="participants")
    user_id = models.UUIDField()

    def __str__(self):
        return str(self.user_id)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user_id"], name="unique_participant"
            )
        ]

class Message(models.Model):

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender_id = models.UUIDField()

    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
