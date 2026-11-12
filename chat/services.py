import json
import uuid

from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from django.db import transaction

from .models import Conversation, Participant


class InvalidEvent(Exception):
    """The event payload is malformed: retrying it will never succeed."""


def parse_friend_payload(data):
    try:
        payload = json.loads(data)
        user_a, user_b = (uuid.UUID(str(u)) for u in payload["user_ids"])
    except (ValueError, TypeError, KeyError) as e:
        raise InvalidEvent(f"bad friend chat payload: {data!r}") from e
    if user_a == user_b:
        raise InvalidEvent("a friend chat needs two different users")
    return user_a, user_b


@sync_to_async
def get_or_create_friend_chat(user_a, user_b):
    """Return (conversation, created). Safe to call twice with the same pair."""
    with transaction.atomic():
        # two separate filters = two joins: the chat must contain user_a AND user_b
        existing = (
            Conversation.objects
            .filter(type=Conversation.Type.FRIEND, participants__user_id=user_a)
            .filter(participants__user_id=user_b)
            .first()
        )
        if existing:
            return existing, False

        conv = Conversation.objects.create(type=Conversation.Type.FRIEND)
        Participant.objects.bulk_create([
            Participant(conversation=conv, user_id=user_a),
            Participant(conversation=conv, user_id=user_b),
        ])
        return conv, True


async def notify_chat_created(conv_id, user_ids):
    """Tell each user's open sockets (if any) that they are in a new chat."""
    channel_layer = get_channel_layer()
    for user_id in user_ids:
        # consumers in group user_<id> will run their chat_created() method
        await channel_layer.group_send(f"user_{user_id}", {
            "type": "chat.created",
            "chat_id": str(conv_id),
        })


async def handle_friend_chat_created(data):
    user_a, user_b = parse_friend_payload(data)
    conv, created = await get_or_create_friend_chat(user_a, user_b)
    # notify even if it already existed: a previous attempt may have crashed
    # after saving but before notifying. The consumer ignores chats it already has.
    await notify_chat_created(conv.id, [user_a, user_b])
    return conv, created


def parse_lobby_payload(data):
    try:
        return uuid.UUID(str(json.loads(data)[  "lobby_id"]))
    except (ValueError, TypeError, KeyError) as e:
        raise InvalidEvent(f"bad lobby chat payload: {data!r}") from e


async def handle_lobby_chat_create(data):
    lobby_id = parse_lobby_payload(data)
    # lobby_id is unique: if Lobby retries the request, it gets the same chat back
    conv, _ = await Conversation.objects.aget_or_create(
        lobby_id=lobby_id, defaults={"type": Conversation.Type.LOBBY}
    )
    return conv


def parse_lobby_player_payload(data):
    try:
        payload = json.loads(data)
        return uuid.UUID(str(payload["lobby_id"])), uuid.UUID(str(payload["user_id"]))
    except (ValueError, TypeError, KeyError) as e:
        raise InvalidEvent(f"bad lobby player payload: {data!r}") from e


async def handle_lobby_player_joined(data):
    lobby_id, user_id = parse_lobby_player_payload(data)
    # get_or_create on both: safe if the event is redelivered or arrives before the chat exists
    conv, _ = await Conversation.objects.aget_or_create(
        lobby_id=lobby_id, defaults={"type": Conversation.Type.LOBBY}
    )
    await Participant.objects.aget_or_create(conversation=conv, user_id=user_id)
    await notify_chat_created(conv.id, [user_id])
