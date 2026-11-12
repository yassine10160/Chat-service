# chat/consumers.py
import json
import uuid
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import Conversation, Message


def chat_group(conversation_id):
    return f"chat_{conversation_id}"


def user_group(user_id):
    return f"user_{user_id}"


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user_id = self.scope['user_id']
        if self.user_id is None:
            # print('i m heeeere')
            await self.close()
            return

        # conversation_id (str) -> Conversation, for every chat this user is in
        self.conversations = {}
        chats = []

        queryset = (
            Conversation.objects
            .filter(participants__user_id=self.user_id)
            .prefetch_related("participants")
        )
        async for conv in queryset:
            self.conversations[str(conv.id)] = conv
            chats.append(self.serialize_chat(conv))
            await self.channel_layer.group_add(chat_group(conv.id), self.channel_name)

        # personal group: lets other processes (the NATS listener) reach this user
        await self.channel_layer.group_add(user_group(self.user_id), self.channel_name)

        await self.accept()
        await self.send_json({"type": "chat_list", "chats": chats, "user_id": self.user_id})

    async def disconnect(self, code):
        # connect() may have closed before these were set
        if getattr(self, "user_id", None) is None:
            return
        for cid in self.conversations:
            await self.channel_layer.group_discard(chat_group(cid), self.channel_name)
        await self.channel_layer.group_discard(user_group(self.user_id), self.channel_name)

    # def get_user_id(self):
    #     # DEV ONLY: read ?user_id=<uuid> from the socket URL. Replace with the JWT user.
    #     params = parse_qs(self.scope["query_string"].decode())
    #     try:
    #         return uuid.UUID(params["user_id"][0])
    #     except (KeyError, ValueError):
    #         return None

    def serialize_chat(self, conv):
        chat = {"id": str(conv.id), "type": conv.type}
        if conv.type == Conversation.Type.FRIEND:
                others = [p.user_id for p in conv.participants.all() if p.user_id != self.user_id]
                chat["friend_id"] = str(others[0]) if others else None
        elif conv.type == Conversation.Type.LOBBY:
            chat["lobby_id"] = str(conv.lobby_id)
        return chat

    # ---------- messages from the browser ----------

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send_error("invalid json format")
            return

        handlers = {
            "send_message": self.handle_send_message,
        }
        handler = handlers.get(data.get("type")) if isinstance(data, dict) else None
        if handler is None:
            await self.send_error("unknown message type")
            return
        await handler(data)

    async def handle_send_message(self, data):
        conv = self.conversations.get(str(data.get("chat_id")))
        if conv is None:
            await self.send_error("you are not in this chat")
            return

        content = data.get("content")
        if not isinstance(content, str) or not content.strip():
            await self.send_error("empty message")
            return

        # lobby chats are temporary: their messages are not stored
        if conv.type == Conversation.Type.LOBBY:
            message_id, created_at = None, timezone.now()
        else:
            message = await Message.objects.acreate(
                conversation=conv, sender_id=self.user_id, message=content
            )
            message_id, created_at = message.id, message.created_at

        await self.channel_layer.group_send(chat_group(conv.id), {
            "type": "chat.message",  # calls chat_message() on every consumer in the group
            "message": {
                "id": message_id,
                "chat_id": str(conv.id),
                "sender_id": str(self.user_id),
                "content": content,
                "created_at": created_at.isoformat(),
            },
        })

    # ---------- events from the channel layer ----------

    async def chat_message(self, event):
        await self.send_json({"type": "chat_message", "message": event["message"]})

    async def chat_created(self, event):
        chat_id = event["chat_id"]
        if chat_id in self.conversations:
            return  # already known (e.g. duplicate notification)

        # reload from the DB, and only if this user is really a participant
        conv = await (
            Conversation.objects
            .filter(id=chat_id, participants__user_id=self.user_id)
            .prefetch_related("participants")
            .afirst()
        )
        if conv is None:
            return

        self.conversations[chat_id] = conv
        await self.channel_layer.group_add(chat_group(conv.id), self.channel_name)
        await self.send_json({"type": "chat_created", "chat": self.serialize_chat(conv)})

    # ---------- helpers ----------

    async def send_json(self, payload):
        await self.send(text_data=json.dumps(payload))

    async def send_error(self, error):
        await self.send_json({"type": "error", "error": error})
