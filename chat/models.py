from django.db import models

class Conversation(models.Model):

    id = models.UUIDField(primary_key=True)
    persist = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Participant(models.Model):

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="participants")
    user_id = models.UUIDField()

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
