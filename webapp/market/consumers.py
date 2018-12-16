import json
import logging
import time

from channels import Group, Channel
from channels.log import setup_logger
from channels.auth import channel_session_user, channel_session_user_from_http

from .post_manager import post

logger = setup_logger(__name__)
logger.setLevel(logging.DEBUG)

# Connected to websocket.connect
@channel_session_user_from_http
def ws_connect(message):
    # Accept connection
    if message.user.is_authenticated:
        message.reply_channel.send({"accept": True})
        Group("users").add(message.reply_channel)
        logger.info("Websocket connected to %s", message.user)
    else:
        message.reply_channel.send({"close": True})
        logger.info("Connection Not allowed for no authenticated user")

# Connected to websocket.receive
@channel_session_user
def ws_message(message):
    # data 형식
    # { worker: worker, method: method_name, args: {keyword arg} }
    if message.user.is_authenticated:
        data = json.loads(message.content["text"])
        data['timestamp'] = time.time()
        logger.info("(send) %s", data)

        if data["worker"] == "manager" and data["args"]["todo"] == "rawdata":
            data['args']['activeinfo'] = post.get_active()

        # 전체 자동 진행 flag
        if data["worker"] == "manager" and "timeframe" in data["args"]\
           and data["args"]["timeframe"] == "all":
            data['args']['auto'] = True
        elif data["worker"] == "manager":
            data['args']['auto'] = False

        Channel(data.pop("worker")).send(data)

# Connected to websocket.disconnect
@channel_session_user
def ws_disconnect(message):
    Group("users").discard(message.reply_channel)
    logger.info("%s disconnected", message.user)


def broker_msg(message):
    Group("users").send({"text": json.dumps(message.content)})
    logger.info("(receive) %s", message.content)


def post_work(message):
    if message.content['method'] == "marketinfo":
        post.save(message.content["data"])
        if message.content['auto']:
            data = {
                "method": "task",
                "timestamp": time.time(),
                "args": {
                    "todo": "rawdata",
                    "timeframe": "day",
                    "auto": True,
                    "activeinfo": post.get_active()
                }
            }
            Channel("manager").send(data)


