import asyncio
import json

from django.conf import settings
from django.core.management.base import BaseCommand
from nats import connect
from nats.errors import TimeoutError
from nats.js.errors import BadRequestError

from chat import services

LOBBY_CREATE_SUBJECT = "chat.lobby.create"

# (stream name, subjects) we consume from JetStream
STREAMS = [
    ("USER_PROFILE_STREAM", "UserProfile.events.*"),
    ("LOBBY_STREAM", "Lobby.events.*"),
]

# JetStream subject -> handler. Add a line here for each new event.
EVENT_HANDLERS = {
    "UserProfile.events.friend_added": services.handle_friend_chat_created,
    "Lobby.events.player_joined": services.handle_lobby_player_joined,
}


class Command(BaseCommand):
    help = "Listen to NATS: lobby requests (request/reply) and service events (JetStream)"

    def handle(self, *args, **options):
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            self.stdout.write("NATS listener stopped")

    async def run(self):
        nc = await connect(settings.NATS_URL)
        js = nc.jetstream()

        # 1. core NATS: Lobby waits for our answer, so the callback must respond()
        await nc.subscribe(LOBBY_CREATE_SUBJECT, cb=self.on_lobby_create)
        self.stdout.write(self.style.SUCCESS(f"Answering requests on '{LOBBY_CREATE_SUBJECT}'"))

        # 2. JetStream: one independent consume loop per stream
        await asyncio.gather(*(self.consume(js, name, subject) for name, subject in STREAMS))

    async def consume(self, js, stream, subject):
        try:
            await js.add_stream(name=stream, subjects=[subject])
        except BadRequestError:
            pass  # stream already exists with another config; keep it
        sub = await js.pull_subscribe(subject, durable="chat-service")
        self.stdout.write(self.style.SUCCESS(f"Consuming '{subject}'"))

        while True:
            try:
                msgs = await sub.fetch(batch=10, timeout=2)
            except TimeoutError:
                continue  # no new events in the last 2s
            for msg in msgs:
                await self.on_event(msg)

    async def on_lobby_create(self, msg):
        try:
            conv = await services.handle_lobby_chat_create(msg.data)
            reply = {"chat_id": str(conv.id)}
        except services.InvalidEvent as e:
            reply = {"error": str(e)}
        except Exception as e:
            self.stderr.write(f"lobby create failed: {e!r}")
            reply = {"error": "internal error"}
        await msg.respond(json.dumps(reply).encode())

    async def on_event(self, msg):
        handler = EVENT_HANDLERS.get(msg.subject)
        if handler is None:
            await msg.ack()  # an event we don't care about
            return
        try:
            await handler(msg.data)
            await msg.ack()
        except services.InvalidEvent as e:
            self.stderr.write(str(e))
            await msg.term()  # broken payload: never redeliver it
        except Exception as e:
            # e.g. database down: no ack, so JetStream redelivers it later
            self.stderr.write(f"{msg.subject} failed, will retry: {e!r}")
