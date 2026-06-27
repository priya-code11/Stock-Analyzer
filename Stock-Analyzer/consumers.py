import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):

        self.user = self.scope["user"]

        if self.user.is_anonymous:
            await self.close()
            return

        self.group_name = f"notif_{self.user.id}"

        print("GROUP JOINED:", self.group_name)

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        print("Connected:", self.user.username)

    async def disconnect(self, close_code):

        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

        print("Disconnected:", self.user.username)

    async def send_notification(self, event):

        print("CONSUMER RECEIVED:", event)

        await self.send(
            text_data=json.dumps({
                "message": event["message"],
                "unread_count": event["unread_count"]
            })
        )