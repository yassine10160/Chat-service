# chat/consumers.py
import json

from channels.generic.websocket import AsyncWebsocketConsumer
from . import models

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # print(f'test: {self.scope['user']}')
        # print(f'my kargs: {self.scope}')
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"
        
        try:
            conversation = await models.Conversation.objects.aget(id=self.conversation_id)
            print(f'convo: {conversation}')
        except models.Conversation.DoesNotExist:
            print("my bad bro")
        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name, {"type": "chat.message", "message": message}
        )

    # Receive message from room group
    async def chat_message(self, event):
        message = event["message"]

        # Send message to WebSocket
        await self.send(text_data=json.dumps({"message": message}))
        