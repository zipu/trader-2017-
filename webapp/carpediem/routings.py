from channels.routing import route
from market.consumers import ws_message, ws_connect, ws_disconnect, broker_msg, post_work

channel_routing = [
    route("websocket.connect", ws_connect),
    route("websocket.receive", ws_message),
    route("websocket.disconnect", ws_disconnect),
    route("web", broker_msg),
    route("post-work", post_work) 
]
