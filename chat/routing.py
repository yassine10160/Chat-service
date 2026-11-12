# chat/routing.py
from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    # one socket per user, carrying all of their chats
    re_path(r"^ws/chat/$", consumers.ChatConsumer.as_asgi()),
]
