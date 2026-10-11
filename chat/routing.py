from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/community/chat/(?P<channel_slug>[\w-]+)/$", consumers.ChatConsumer.as_asgi()),
    re_path(r"ws/dm/(?P<session_id>[\w-]+)/$", consumers.DirectMessageConsumer.as_asgi()),
    re_path(r"ws/notifications/$", consumers.NotificationConsumer.as_asgi()),
]
