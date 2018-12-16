# -*- coding: utf-8 -*-
import sys, os, logging, re, time, traceback, codecs, json
from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal as D
from shutil import copyfile
from copy import deepcopy
import tables as tb
import numpy as np


from ebest.xingAPI import Session, XAEvents, Query, Real
from ebest.meta import TR, Helper

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..\\..\\data')
sys.path.append(DATA_DIR)

from dbtools import load_products, save_products, ezdate
from model import Density, OHLC

# 제외상품 목록
EXCLUSIONS = ['E7','FDXM', 'HMCE','HMH','J7','M6A','M6B','M6E','MCD','MGC','MJY','QC','QG','QM',\
              'VX','XC','XK','XW','YG','YI','MP','CUS']

class DBmanager:
    """
    데이터 수집 및 갱신하는 클래스
    설명:
        - xing api를 이용해 시장정보 및 거래정보를 수집
        - 종목정보 수집 -> 검증 -> DB에 저장
        - 일간 데이터, 분 데이터 수집
        - 액티브 월물 채택 기준: 근월물과 차월물 중 3 거래일 연속 거래량이 더 큰 월물 채택
    """

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger()
        self.session = Session(self, demo=True)
        self.tasks = []
        self.messages = deque() #이벤트 결과 저장용 메세지큐

    # 10분당 조회 tr 200회 제한 확인용 매서드
    def check_req_limit(self, tr):
        count = self.query.get_tr_count_request(tr.CODE)
        if count >= 199:
            delta = 60 * 10 - (time.time() - self.timer)+5
            if delta < 0:
                delta = 600
            self.logger.info("need to sleep %s sec", delta)
            time.sleep(delta)
            self.timer = time.time()
        else:
            time.sleep(tr.TR_PER_SEC+0.1) #초당 조회제한


    def work(self, **args):
        """ 
        tasks : ['products','day','minute', 'backup']
        """
        if not self.tasks:
            self.logger.info("No more work to do!")
            return

        elif not self.session.is_connected():
            self.login(key=args['key'] if 'key' in args else None)

        else:
            #날짜
            self.today = ezdate('today')
            self.timer = time.time() #조회 제한 용 타이머

            task = self.tasks.pop(0)
            # 백업
            if task == 'backup':
                self.backup()

            # 상품정보 업데이트
            elif task == "products":
                self.request_productsinfo()

            elif task == "ohlc" or task == "density":
                #open DB
                db_dir = os.path.join(DATA_DIR, 'market.hdf5')
                filters = tb.Filters(complib='blosc', complevel=9)
                self.h5file = tb.open_file(db_dir, mode="a", filters=filters)
                
                self.products_l = list(load_products().values())
                self.codelength = len(self.products_l)
                
                self.message = [] #중요 메시지 마지막에 보여주는 용도
                
                # 신규 종목 db 생성
                for product in self.products_l:
                    if not hasattr(self.h5file.root, product['symbol']):
                        node = self.h5file.create_group('/', product['symbol'] , product['name'])
                        ohlc = self.h5file.create_table(node, "OHLC", OHLC, "Daily OHLC Data")
                        #ohlc.cols.date.create_csindex()
                        self.h5file.create_table(node, "Density", Density, "Minutely Density Data")
                        self.h5file.flush()


                if task == "ohlc":
                    self.logger.info("TASK : Updating Daily OHLC Data")
                    self.get_ohlc_data()
                elif task == 'density':
                    self.logger.info("TASK : Updating Density Data")
                    self.get_density_data()

    def flush(self):
        del self.today
        del self.timer
        if hasattr(self, 'h5file'): del self.h5file
        if hasattr(self, 'products_l'): del self.products_l
        if hasattr(self, 'codelength'): del self.codelength
        if hasattr(self, 'products'): del self.products
        if hasattr(self, 'cursor'): del self.cursor
        if hasattr(self, 'message'): del self.message
        if hasattr(self, 'lastday'): del self.lastday
        if hasattr(self, 'fields'): del self.fields
    
    # 파일 백업
    def backup(self):
        src = os.path.join(DATA_DIR, 'market.hdf5')
        dst_file = 'market_bak/market_'+self.today.str('%Y%m%d%H%M%S')+'.hdf5'
        dst = os.path.join(DATA_DIR, dst_file)
        copyfile(src, dst)
        self.logger.info("file has backed up to %s",dst_file)
        self.work()

    
    ######################################################################
    ##                         로그인                                   ##
    ######################################################################
    def login(self, key=None):
        """ 로그인 """
        if not key:
            key = input("Insert login key: ")
        fdir = os.path.join(DATA_DIR, 'dump')
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

    def parse_err_code(self, trcode, errcode):
        ret = self.session.get_error_message(errcode)
        msg = '({}) {}'.format(trcode, ret)
        self.logger.warning(msg)

    @XAEvents.on('OnLogin')
    def __login(self, code, msg):
        self.logger.info("(%s): %s", code, msg)
        if code=='0000':
            self.work()

    @XAEvents.on('OnReceiveMessage')
    def _msg_receiver(self, syserr, code, msg):
        if syserr: #True면 시스템 오류
            self.logger.warning("OnReceiveMessage: System Error : (%s) %s", code, msg)
        else:
            self.logger.debug("OnReceiveMessage: (%s) %s", code, msg)


    ######################################################################
    ##                         products-info update                     ##
    ######################################################################
    #1. 전체 종목 정보를 요청
    def request_productsinfo(self):


        self.logger.info("TASK: Updating market information")
        self.tr = TR.o3101() #해외선물 종목정보

        self.query = Query(self, self.tr.CODE)
        fields = dict(gubun='')

        errcode = self.query.request(self.tr.INBLOCK, fields)
        if errcode < 0:
            self.parse_err_code(self.tr.CODE, errcode)

    #2. 종목 리스트를 정리
    @XAEvents.on('OnReceiveData', code='o3101')
    def __marketinfo(self, code):
        if self.tr.methodname != 'request_productsinfo':
            return

        self.products = dict()
        outblock = self.tr.OUTBLOCK
        cnt = self.query.get_block_count(outblock)
        for i in range(cnt):
            market = self.query.get_field_data(outblock, 'GdsCd', i) #시장구분
            market = Helper.market_symbol(market)
            symbol = self.query.get_field_data(outblock, 'BscGdsCd', i) #상품코드
            code = self.query.get_field_data(outblock, 'Symbol', i) #종목코드
            codename = self.query.get_field_data(outblock, 'SymbolNm', i) #종목명
            name = self.query.get_field_data(outblock, 'BscGdsNm', i) #기초 상품명
            # o3101 'LstngYr이 이상하게 들어와서 codename parsing으로 긴급조치함(170808)
            #month = datetime(
            #    int(self.query.get_field_data(outblock, 'LstngYr', i)),
            #    int(Helper.get_month(self.query.get_field_data(outblock, 'LstngM', i))),
            #    1
            #) #월물
            month = datetime(int(codename[-8:-4]), int(codename[-3:-1]), 1)

            # 마이크로 상품, 거래량 적은 상품 제외
            if symbol in EXCLUSIONS:
                continue 

            if symbol not in self.products.keys():
                self.products[symbol] = dict(
                    market=market, #시장구분
                    symbol=symbol, #상품구분
                    name=name, #상품명
                    currency=self.query.get_field_data(outblock, 'CrncyCd', i), #통화구분
                    notation=self.query.get_field_data(outblock, 'NotaCd', i), #진법구분
                    tick_unit=D(self.query.get_field_data(outblock, 'UntPrc', i)), #틱 단위
                    tick_value=D(self.query.get_field_data(outblock, 'MnChgAmt', i)), #틱 가치
                    rgl_factor=self.query.get_field_data(outblock, 'RgltFctr', i), #가격 조정계수
                    open_time=self.query.get_field_data(outblock, 'DlStrtTm', i), #거래시작시간
                    close_time=self.query.get_field_data(outblock, 'DlEndTm', i), #거래종료시간
                    is_tradable=self.query.get_field_data(outblock, 'DlPsblCd', i), #거래가능구분
                    open_margin=D(self.query.get_field_data(outblock, 'OpngMgn', i)), #개시증거금
                    decimals=int(self.query.get_field_data(outblock, 'DotGb', i)), #유효소숫점자리수
                    last_update=datetime.now().strftime('%Y%m%d%H%M'), #마지막 업데이트
                    codes=[]
                )

            # 종목별 정리
            self.products[symbol]['codes'].append(dict(
                code=code, #월물코드
                month=month, #월물
                codename=codename, #종목명
                symbol=symbol #심볼
            ))

        # sorting month
        for product in self.products.values():
            product['codes'].sort(key=lambda x: x['month'])
            product['codes'] = product['codes'][:3] #최근 3개 월물 저장

        self.allcodes = [x for product in self.products.values() for x in product['codes']]
        self.collect_trade_data()

    #3. 종목 거래정보 수집
    def collect_trade_data(self):
        self.tr = TR.o3103()
        self.query = Query(self, self.tr.CODE)
        self.code = self.allcodes.pop()
        field = dict(
            shcode = self.code['code'],
            ncnt = 60,
            readcnt=24,
            cts_date='',
            cts_time=''
        )

        #조회요청 
        errcode = self.query.request(self.tr.INBLOCK, field)
        if errcode < 0:
            self.parse_err_code(self.tr.CODE, errcode)
        else:
            self.logger.info("Receving %s (remains: %s)", self.code['codename'], len(self.allcodes))
    
    @XAEvents.on('OnReceiveData', code='o3103')
    def __collect_trade_data(self, code):
        if self.tr.methodname != 'collect_trade_data':
            return

        outblock = self.tr.OUTBLOCK1
        cnt = self.query.get_block_count(outblock)
        prices = []
        vol = 0
        for i in range(cnt):
            prices.append(D(self.query.get_field_data(outblock, 'open', i))) #시가
            prices.append(D(self.query.get_field_data(outblock, 'close', i))) #종가
            vol += int(self.query.get_field_data(outblock, 'volume', i)) #거래량
        
        self.code['volume'] = vol
        
        # 기준가격(price) 정하기 (시가 + 종가  평균)
        digit = [x['decimals'] for x in self.products.values() if self.code in x['codes']][0]
        tickunit = [x['tick_unit'] for x in self.products.values() if self.code in x['codes']][0]
        self.code['ec_price'] = round((np.mean(prices) // tickunit) * tickunit, digit)  if prices else D('0')

        # 조회제한 확인
        self.check_req_limit(self.tr)

        # 연속조회
        if self.allcodes:
            self.collect_trade_data()

        else:
            self.set_active()

    # 4. 액티브 월물 결정
    # 전일 기준 거래량이 가장 큰 월물을 액티브 월물로 결정함
    def set_active(self):
        for product in self.products.values():
            product['active'] = deepcopy(max(product['codes'], key=lambda x: x['volume']))
            product['active']['activated_date'] = self.today.str()
            product['active']['price_gap'] = D('0')
        
        self.verification()

    #5. 기존 상품정보와 비교
    def verification(self):
        old = load_products()
        if old:
            for symbol, product in self.products.items():
                # case 1. 신규 생성된 상품
                if symbol not in old:
                    continue

                else:
                    cur_ac = product['active'] #신규 액티브
                    old_ac = old[symbol]['active'] #구 액티브

                # case 2. 액티브 웜물이 기존보다 앞서거나 같은 경우: pass
                if cur_ac['month'] <= old_ac['month']:
                    product['active'] = old_ac

                # case 3. 신규 액티브 월물이 갱신된 경우: 갱신
                elif cur_ac['month'] > old_ac['month']:
                    newprice = [x['ec_price'] for x in old[symbol]['codes'] if x['code'] == cur_ac['code']][0]
                    lastprice = [x['ec_price'] for x in old[symbol]['codes'] if x['code'] == old_ac['code']][0]
                    tick = product['tick_unit']
                    cur_ac['price_gap'] = round( (newprice - lastprice)//tick * tick , product['decimals'])
                    self.logger.info("Active month of %s has changed with price gap %s (%s -> %s) "\
                                 , product['name'], cur_ac['price_gap'], old_ac['month'], cur_ac['month'])

        save_products(self.products)
        self.logger.info("*** Products Information Successfully Updated ***")
        self.flush()
        self.work()            
        

    ######################################################################
    ##                         Daily OHLC Update                        ##
    ######################################################################
    def get_ohlc_data(self):
        
        #tr 정보
        self.tr = TR.o3108()
        self.query = Query(self, self.tr.CODE)

        #db 정보
        self.product = self.products_l.pop()
        symbol = self.product['symbol']
        self.cursor = getattr(self.h5file.root, symbol).OHLC #db 커서
        self.lastday = ezdate(max(self.cursor.cols.date, default=self.today.delta(-3).stamp())) #최근 저장된 날짜
        startday = self.lastday.delta(1) #시작일
        
        # db에 액티브월물 저장 안되어있으면 저장하기
        if not hasattr(self.cursor.attrs, 'active'):
            self.cursor.attrs.active = self.product['active']['code']

        active = self.cursor.attrs.active #db에 저장된 액티브 월물코드

        # 액티브 월물이 변경된 경우: 선 갭보정 후 다운
        if self.product['active']['code'] != active:
            #digit = self.active['decimal_places'] #소숫점자릿수(반올림용)
            price_gap = self.product['active']['price_gap']
            self.cursor.cols.open[:] = self.cursor.cols.open[:] + price_gap
            self.cursor.cols.high[:] = self.cursor.cols.high[:] + price_gap
            self.cursor.cols.low[:] = self.cursor.cols.low[:] + price_gap
            self.cursor.cols.close[:] = self.cursor.cols.close[:] + price_gap
            self.cursor.attrs.active = self.product['active']['code'] # db에 새로운 액티브 코드 저장
            self.cursor.flush()
            self.message.append("!!! %s Data Has been changed up by %s from %s"%\
                             (self.product['name'], price_gap, self.lastday.str()))

        self.fields = dict(
            shcode=self.product['active']['code'],
            gubun=0, #일별
            qrycnt=500,
            sdate=startday.str(),
            edate=self.today.delta(-1).str(),
            cts_date='',
        )

        #조회 요청
        errcode = self.query.request(self.tr.INBLOCK, self.fields)
        if errcode < 0:
            self.parse_err_code(self.tr.CODE, errcode)

    @XAEvents.on('OnReceiveData', code='o3108')
    def _on_get_ohlc_data(self, code):
        if self.tr.methodname != 'get_ohlc_data':
            return
        data = []
        
        shcode = self.query.get_field_data(self.tr.OUTBLOCK, 'shcode', 0) #종목코드
        cts_date = self.query.get_field_data(self.tr.OUTBLOCK, 'cts_date', 0) #연속일자

        cnt = self.query.get_block_count(self.tr.OUTBLOCK1)
        for i in range(cnt):
            date = self.query.get_field_data(self.tr.OUTBLOCK1, 'date', i) #날짜
            open = self.query.get_field_data(self.tr.OUTBLOCK1, 'open', i) #시가
            high = self.query.get_field_data(self.tr.OUTBLOCK1, 'high', i) #고가
            low = self.query.get_field_data(self.tr.OUTBLOCK1, 'low', i) #저가
            close = self.query.get_field_data(self.tr.OUTBLOCK1, 'close', i) #종가
            volume = self.query.get_field_data(self.tr.OUTBLOCK1, 'volume', i) #거래량

            #날짜가 이상할때가 있음.
            try:
                date = ezdate(date)
                #ndate = np.datetime64(datetime.strptime(date, '%Y%m%d')).astype('uint64')/1000000
                #sdate = datetime.strptime(date, '%Y%m%d').strftime('%Y-%m-%d')
            except:
                self.logger.warning("%s has a missing DATE or something is wrong", shcode)
                self.logger.error(traceback.format_exc())
                continue

            #거래량이 1  미만이면 버림
            if int(volume) < 1:
                self.logger.info("%s with volume %s will be passed at %s", shcode, volume, date.str())
                continue

            if np.rint(date.stamp()) <= np.rint(self.lastday.stamp()):
                self.logger.warning("Last date of %s in DB matched at %s", shcode, date.str())
                continue

            ndate = date.stamp()
            if self.cursor.read_where('date==ndate').size:
                self.logger.info("duplicated date: %s", date.str())
                continue
            datum = (date.stamp(), open, high, low, close, volume)
            data.append(datum)

        count = self.query.get_tr_count_request(self.tr.CODE)

        if data:
            msg = "Updating daily: %s at  %s, TR: %s, (%s/%s)"\
                  %(self.product['name'], date.str(), count, len(self.products_l), self.codelength)
            self.logger.info(msg)
            self.cursor.append(data)
            self.cursor.flush()
        else:
            msg = "Nothing to update: %s , TR: %s (%s/%s)"\
                  %(self.product['name'], count, len(self.products_l), self.codelength)
            self.logger.info(msg)

        # 10분당 조회 tr 200회 제한
        self.check_req_limit(self.tr)

        if cts_date != '00000000':
            self.fields['cts_date'] = cts_date
            errcode = self.query.request(self.tr.INBLOCK, self.fields, bnext=True)
            if errcode < 0:
                self.parse_err_code(self.tr.CODE, errcode)

        else:
            if self.products_l:
                self.get_ohlc_data()
            else:
                for msg in self.message:
                    self.logger.info(msg)
                self.logger.info("** Daily Data updated completely **")

                self.h5file.close()
                self.flush()
                self.work()

    ######################################################################
    ##                         Minute Data Update                       ##
    ######################################################################
    def get_density_data(self):
        """ 분봉 데이터 받기 """
        #tr 정보
        self.tr = TR.o3103()
        self.query = Query(self, self.tr.CODE)

        #db 정보
        self.product = self.products_l.pop()
        symbol = self.product['symbol']
        
        self.cursor = getattr(self.h5file.root, symbol).Density
        self.lastdate = ezdate(max(self.cursor.cols.date, default=self.today.delta(-2).stamp())) #최근 저장된 날짜
        self.flag = False #last date 매칭 되었을때 사용

        if not hasattr(self.cursor.attrs, 'active'):
            self.cursor.attrs.active = self.product['active']['code']
        
        active = self.cursor.attrs.active #db에 저장된 종목 코드

        # 액티브 월물이 변경된 경우: 선 갭보정 후 다운
        if self.product['active']['code'] != active:
            price_gap = self.product['active']['price_gap'] #가격 차이
            #데이터 변환
            self.cursor.cols.price[:] = self.cursor.cols.price[:] + price_gap
            self.cursor.attrs.active = self.product['active']['code'] #새로운 액티브 코드 저장
            self.cursor.flush()
            self.message.append("!!!CASE1: %s Data Has been changed up by %s from %s"%\
                             (self.product['name'], price_gap, self.lastdate.str('s')))

        self.fields = dict(
            shcode=self.product['active']['code'],
            ncnt=1, #분단위
            readcnt=500,
            cts_date='',
            cts_time='',
        )
        # 로깅
        self.logger.info("Started to get MINUTE data : %s upto %s",
                         self.product['name'], self.lastdate.str('s'))

        # 조회 요청 
        errcode = self.query.request(self.tr.INBLOCK, self.fields)
        if errcode < 0:
            self.parse_err_code(self.tr.CODE, errcode)

    @XAEvents.on('OnReceiveData', code='o3103')
    def _on_get_density_data(self, code):
        if self.tr.methodname != 'get_density_data':
            return 
        shcode = self.query.get_field_data(self.tr.OUTBLOCK, 'shcode', 0) #종목코드
        cts_date = self.query.get_field_data(self.tr.OUTBLOCK, 'cts_date', 0) #연속일자
        cts_time = self.query.get_field_data(self.tr.OUTBLOCK, 'cts_time', 0) #연속시간
        timediff = int(self.query.get_field_data(self.tr.OUTBLOCK, 'timediff', 0)) * (-1) #시차

        cnt = self.query.get_block_count(self.tr.OUTBLOCK1)
        for i in range(cnt):
            date = self.query.get_field_data(self.tr.OUTBLOCK1, 'date', i) #날짜
            dtime = self.query.get_field_data(self.tr.OUTBLOCK1, 'time', i) #시간
            high = float(self.query.get_field_data(self.tr.OUTBLOCK1, 'high', i)) #고가
            low = float(self.query.get_field_data(self.tr.OUTBLOCK1, 'low', i)) #저가
            volume = int(self.query.get_field_data(self.tr.OUTBLOCK1, 'volume', i)) #거래량

            items = []

            #날짜가 이상할때가 있음.
            try:
                ndate = np.datetime64(datetime.strptime(date+dtime, '%Y%m%d%H%M%S')) \
                         + np.timedelta64(timediff, 'h')
                date = ezdate(ndate)
                #ndate = ndate.astype('uint64')/1000000
                #sdate = datetime.strptime(date+dtime, '%Y%m%d%H%M%S') + timedelta(hours=timediff)
                #sdate = sdate.strftime('%Y-%m-%dT%H:%M:%S')
            except:
                self.logger.warning("%s has a missing DATE or something is wrong %s", shcode, date.str('s'))
                self.logger.error(traceback.format_exc())
                continue


            #거래량이 1 미만이면 버림
            if int(volume) < 1:
                self.logger.info("%s with volume %s will be passed at %s", shcode, volume, sdate)
                continue

            #db에 저장된 최근 날짜보다 이전이면 끝냄
            if np.rint(date.stamp()) <= np.rint(self.lastdate.stamp()):
                self.flag = True
                self.logger.warning("Last date of %s in DB matched at %s", shcode, date.str('s'))
                break
            
            # 날짜 겹치면 버림
            ndate = date.stamp()
            if self.cursor.read_where('date==ndate').size:
                self.logger.info("duplicated date: %s", date.str('s'))
                continue

            else:
                digit = self.product['decimals']
                tickunit = float(self.product['tick_unit'])
                
                if round(low, digit) == round(high, digit):
                    item = (date.stamp(), round(low, digit), volume)
                    items.append(item)

                else:
                    length = (high-low)/tickunit + 1
                    length = np.rint(length)
                    value = volume/length

                    if np.isinf(value) or (value < 0.1): #inf value 종종 생겨서..
                        self.logger.warning("wrong volume: %s, length: %s at %s",
                                            volume, length, date.str('s'))
                        continue

                    for price in np.arange(round(low, digit), high - tickunit/2, tickunit):
                        item = (date.stamp(), round(price, digit), value)
                        items.append(item)

                if items:
                    self.cursor.append(items)
                    self.cursor.flush()
        count = self.query.get_tr_count_request(self.tr.CODE)

        if 'items' in locals() and items:
            msg = "Updating Minute data: %s, TR: %s, (%s/%s)"\
                  %(self.product['name'], count, len(self.products_l), self.codelength)
            self.logger.info(msg)
        else:
            msg = "Nothing to update: %s, TR: %s, (%s/%s)"\
                 %(self.product['name'], count, len(self.products_l), self.codelength)
            self.logger.info(msg)

        # 10분당 조회 tr 200회 제한
        self.check_req_limit(self.tr)

        if (cts_date == '00000000') or self.flag:
            if 'date' in locals():
                self.logger.info("Reached last date at  %s", date.str('s'))

            if self.products_l:
                self.get_density_data()
            else:
                for msg in self.message:
                    self.logger.info(msg)
                self.logger.info("** Minute Data updated completely **")
                self.h5file.close()
                self.flush()
                self.work()
                
        elif cts_date != '00000000':
            self.fields['cts_date'] = cts_date
            self.fields['cts_time'] = cts_time
            errcode = self.query.request(self.tr.INBLOCK, self.fields, bnext=True)
            if errcode < 0:
                self.parse_err_code(self.tr.CODE, errcode)
