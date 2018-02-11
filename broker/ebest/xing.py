import sys
import os
import logging
import codecs
from collections import namedtuple, defaultdict
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSlot, pyqtSignal, QVariant

from trader.util import util
from .xingAPI import Session, XAEvents, Query, Real
from .meta import TR, Helper
from db_manager.manager import Factory

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..\\..\\data')

class eBest(QObject):
    """
     Event Handler Usage:
        Any method that decorated with @XAEvents.on("<some_event>") will act as
        a event handler for "some_event". There could be optional keyword argument
        'code' for 'OnReceiveData'
        ex) @KiwoomAPI.on("OnReceiveData", code='0001')
            def any_method(self, *args):
                //Do something
    """

    bridge = pyqtSignal(str, QVariant)
    loginEvent = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.ovc = Real(self, TR.OVC.CODE) #실시간 체결 


    ######################################################################
    ##                    접속 및 메시지 관련                            ##
    ######################################################################
    
    @pyqtSlot(bool)
    def server_type(self, flag):
        self.session = Session(self, demo=flag)
    
    @pyqtSlot(result=QVariant)
    def login(self):
        """ 로그인 """

        with open('data/dump', 'r') as f:
            s = f.read()
            a = s.split('\\')
            myid = Helper.decrypt('0318440371', codecs.decode(a[0], "hex")).decode("utf-8")
            pwd = Helper.decrypt('0318440371', codecs.decode(a[1], "hex")).decode("utf-8")

        if self.session.connect_server():
            if self.session.login(myid, pwd):
                return {'succeed': True}        # error 로깅

        err = self.session.get_last_error()
        errmsg = self.session.get_error_message(err)
        self.logger.info('Error message: %s', errmsg)
        return {'succeed': False}

    @pyqtSlot()
    def quit(self):
        self.session.disconnect_server()

    @pyqtSlot(result=QVariant)
    def is_connected(self):
        if self.session.is_connected():
            return {'succeed': True}
        else:
            return {'succeed': False}

    def parse_err_code(self, trcode, errcode):
        ret = self.session.get_error_message(errcode)
        msg = '({}) {}'.format(trcode, ret)
        self.bridge.emit('onReceiveMsg', msg)
        self.logger.warning(msg)


    @XAEvents.on('OnReceiveMessage')
    def _msg_receiver(self, syserr, code, msg):
        if syserr: #True면 시스템 오류
            self.logger.info("OnReceiveMessage: System Error : %s", syserr)
        else:
            self.logger.info("OnReceiveMessage: (%s) %s", code, msg)

    @XAEvents.on('OnLogin')
    def _on_login(self, code, msg):
        self.bridge.emit('onEventConnect', 0)
        self.logger.info("(%s): %s", code, msg)

    @XAEvents.on('OnDisconnect')
    def _on_disconnect(self):
        self.bridge.emit('onEventConnect', -1)
        self.logger.info('서버와의 연결이 끊겼습니다')


    ######################################################################
    ##                         실시간 데이터 관련                         ##
    ######################################################################
    @pyqtSlot(str)
    def unadvise_real_data(self, code):
        if code == 'all':
            self.ovc.unadvise_real_data()
            self.logger.info("모든종목 실시간 연결 해제")
        else:
            self.ovc.unadvise_real_data_with_key(code)
            self.logger.info("선택종목 실시간 연결 해제 : %s", code)

    @XAEvents.on('OnReceiveRealData', code='OVC')
    def _on_realdata(self, code):
        # diff를 real로 받을 필요가 있나? 현재가 - 정산가 하면 되잖아?

        #data = self.ovc.get_block_data(TR.OVC.OUTBLOCK)
        symbol = self.ovc.get_field_data(TR.OVC.OUTBLOCK, 'symbol')
        curpr =self.ovc.get_field_data(TR.OVC.OUTBLOCK, 'curpr')
        ydiffpr = self.ovc.get_field_data(TR.OVC.OUTBLOCK, 'ydiffpr')
        # 2: 상승, 5 : 하락
        ydiffSign = self.ovc.get_field_data(TR.OVC.OUTBLOCK, 'ydiffSign')

        data = [symbol, curpr, ydiffpr, ydiffSign]
        
        self.bridge.emit("onRealPrice", data)



    ######################################################################
    ##                         Initialization                           ##
    ######################################################################

    @pyqtSlot(result=QVariant)
    def get_all_products(self):
        """ 전체종목의  리스트를 불러온다 """
        return util.load('marketinfo')



    ######################################################################
    ##                         관심종목 화면                             ##
    ######################################################################
    @pyqtSlot(QVariant)
    def fav_screen(self, favlist):
        """
        inputValue(list) : ["6AM16","CLN16","ZFM16","ZWN16"]
        """

        tr = TR.o3107
        self.query = Query(self, tr.CODE)
        self.query.set_block_count(tr.INBLOCK, len(favlist)) #블럭 갯수

        fields = []
        for item in favlist:
            fields.append(dict(symbol=item))

        errcode = self.query.request(tr.INBLOCK, fields)
        if errcode < 0:
            self.parse_err_code(tr.CODE, errcode)
        
        #실시간 등록 ==> 얘 그냥 javascript에서 처리
        else: 
            self.unadvise_real_data('all')
            # 선택된 종목 제외한 종목들만 unadvise 하는거 추가
            for item in favlist:
                self.ovc.set_field_data(TR.OVC.INBLOCK, 'symbol', item)
                self.ovc.advise_real_data()


    @XAEvents.on('OnReceiveData', code='o3107')
    def _on_fav_screen(self, code):
        tr = TR.o3107
        data = defaultdict(list)
        cnt = self.query.get_block_count(tr.OUTBLOCK)
        for i in range(cnt):
            code = self.query.get_field_data(tr.OUTBLOCK, 'symbol', i) #종목코드
            price = self.query.get_field_data(tr.OUTBLOCK, 'price', i) #현재가
            diff = self.query.get_field_data(tr.OUTBLOCK, 'change', i) #전일대비
            sign = self.query.get_field_data(tr.OUTBLOCK, 'sign', i) #전일대비 기호
            data[code] = [price, diff, sign]
        self.bridge.emit("_on_fav_screen", dict(data))


    ######################################################################
    ##                             Chart Screen                         ##
    ######################################################################
    @pyqtSlot(QVariant, result=QVariant)
    def get_density(self, product):
        """
         db에서 density data를 로드하는 매소드 
        """
        self.factory = Factory(product)

        # 진법 변환된 가격 데이타로 변경
        xticks = []
        for price in self.factory.xticks:
            xticks.append(str(price))
            #xticks.append(self.GetConvertPrice(product['code'], str(price), 1))

        data = {
            'x_ticks' : xticks,
            'density' : self.factory.density,
            'density_diff' : self.factory.density_diff(product['cutsize'])
        }
        return data

    
    @pyqtSlot(int, result=QVariant)
    def get_density_diff(self, length):
        return self.factory.density_diff(length)