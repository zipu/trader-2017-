import sys
import os
import logging
import time
import codecs

from channels import Channel

from ebest.xingAPI import Session, XAEvents, Query, Real
from ebest.meta import TR, Helper

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..\\..\\data')

class Broker:

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.ovc = Real(self, TR.OVC.CODE)
        self.session = Session(self, demo=True)

    def reply(self, method, data):
        Channel("web").send({
            "worker": "broker",
            "method": method,
            "data": data
        })

    ######################################################################
    ##                    접속 및 메시지 관련                            ##
    ######################################################################
    def parse_error_code(self, trcode, errcode):
        ret = self.session.get_error_message(errcode)
        msg = '({}) {}'.format(trcode, ret)
        self.logger.warning(msg)
    
    def login(self, key):
        """ 로그인 """
        fdir = os.path.join(BASE_DIR, 'dump')
        with open(fdir, 'r') as f:
            #s = f.read()
            a = f.read().split('\\')
            i = Helper.decrypt(key, codecs.decode(a[0], "hex")).decode("utf-8")
            p = Helper.decrypt(key, codecs.decode(a[1], "hex")).decode("utf-8")

        if self.session.connect_server():
            if self.session.login(i, p):
                self.logger.info("로그인 시도")

        else:
            err = self.session.get_last_error()
            errmsg = self.session.get_error_message(err)
            self.logger.info('Error message: %s', errmsg)

    def quit(self):
        """ 세션 종료 """
        self.session.disconnect_server()

    def is_connected(self):
        """ 연결 상태 """
        return True if self.session.is_connected() else False


    @XAEvents.on('OnReceiveMessage')
    def _msg_receiver(self, syserr, code, msg):
        if syserr: #True면 시스템 오류
            data = "System Error: %s"%syserr
            self.logger.info("OnReceiveMessage: System Error : %s", syserr)
        else:
            data = dict(code=code, message=msg)
            self.logger.info("OnReceiveMessage: (%s) %s", code, msg)
        self.reply("OnReceiveMessage", data)

    @XAEvents.on('OnLogin')
    def _login_on(self, code, msg):
        self.reply("login", dict(msg=msg, code=code))
        self.logger.info("(%s): %s", code, msg)


    @XAEvents.on('OnDisconnect')
    def _disconnect_on_Broker(self):
        self.reply("OnDisconnect", "서버와의 연결이 끊겼습니다")
        self.logger.info('서버와의 연결이 끊겼습니다')
