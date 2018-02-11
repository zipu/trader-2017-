import os
import win32com.client
import pythoncom
import logging
from collections import defaultdict

RES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Res')

class XAEvents:
    """
        Event handler class
    """

    __events = dict(
        OnLogin=[], # 서버와의 로그인이 끝나면 발생 (args: code, msg)
        OnDisconnect=[], # 서버와의 연결이 끊어졌을때 발생
        OnReceiveData=defaultdict(list), # 서버로부터 데이터를 수신했을때 발생
        OnReceiveMessage=[], # 서버로부터 메시지를 수신했을 때 발생
        OnReceiveChartRealData=[], # 차트 지표데이터 조회시, 실시간 자동 등록으로 "1"로 했을 경우 발생
        OnReceiveRealData=defaultdict(list), # 서버로부터 데이터를 수신했을때 발생
        OnreceiveLinkData=[] # HTS로부터 연동 정보를 수신했을때 발생
    )

    def __init__(self):
        self._event_connector(XAEvents.__events)

    def _event_connector(self, events):
        for event in events.keys():
            if events[event]:
                setattr(XAEvents, event, self.trigger(event))

    @staticmethod
    def on(event, code=None):
        """ Register event handlers """
        def decorator(func):
            # tagging classname to the handler
            func.__name__ = func.__name__ + '_from_' + func.__qualname__.split('.')[0]
            if event in ['OnReceiveData', 'OnReceiveRealData']:
                XAEvents.__events[event][code].append(func)
            else:
                XAEvents.__events[event].append(func)
        return decorator

    def trigger(self, event):
        """ Call appropriate event handlers when event comes from the server """
        def triggered(*args):
            if event in ['OnReceiveData', 'OnReceiveRealData']:
                handlers = XAEvents.__events[event][args[1]]
            else:
                handlers = XAEvents.__events[event]

            for func in handlers:
                # execute only the functions that include classname of the instance
                if func.__name__.split("_from_")[1] == self.instance.__class__.__name__:
                    func(self.instance, *args[1:])
        return triggered


class Session:

    def __init__(self, instance, demo=False):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        XAEvents.instance = instance #event class에 current instance를 넘김
        pythoncom.CoInitialize()
        client = win32com.client.DispatchEx("XA_Session.XASession")
        self.xing = win32com.client.DispatchWithEvents(client, XAEvents)
        self.demo = demo  #모의 서버

    def connect_server(self):
        """
            서버에 연결합니다
            args:
                virtual(boolean) : 모의서버 접속하는 경우 True
            returns:
                - 연결성공: True, 연결실패: False
                - GetLastError()로 에러 코드를 구할 수 있습니다.
        """
        address = 'demo.ebestsec.co.kr' if self.demo else 'hts.ebestsec.co.kr'
        return self.xing.ConnectServer(address, 20001)

    def disconnect_server(self):
        """
            서버와의 연결 종료
        """
        self.xing.DisconnectServer()
        self.logger.info("서버와의 연결을 종료하였습니다")

    def is_connected(self):
        """
            서버와의 연결상태 확인
            returns - 서버 연결시 True, 아닐 경우 False
        """
        return self.xing.IsConnected()

    def login(self, id, pwd):
        """
            서버에 로그인 합니다
            args:
                person(named tuple) : 개인 정보
                {
                    id(string): 아이디,
                    pwd(string): 비밀번호,
                    certpwd(string): 공인인증 비밀번호
                }
            returns:
                성공: True, 실패: False
        """
        return self.xing.Login(id, pwd, '', 0, 0)

    
    def get_account_list_count(self):
        """ 보유중인 계좌의 개수를 취득합니다 """
        return self.xing.GetAccountListCount()

    def get_account_list(self, cnt):
        """ 보유중인 계좌 목록 중에서, 인덱스에 해당하는 계좌를 취득합니다 """
        return self.xing.GetAccountList(cnt)

    def get_account_name(self, account):
        """ 
            계좌명을 취득합니다
            - account : string
        """
        return self.xing.GetAccountName(account)

    def get_acct_detail_name(self, account):
        """
            계좌 상세명을 취득합니다
            - account : string
        """
        return self.xing.GetAcctDetailName(account)

    def get_acct_nick_name(self, account):
        """
            계좌 별명을 취득합니다
            - account: string
        """
        return self.xing.GetAcctNickName(account)

    def get_last_error(self):
        """마지막에 발생한 에러 코드 값을 취득합니다"""
        return self.xing.GetLastError()

    def get_error_message(self, errcode):
        """에러 코드에 해당하는 에러 정보를 취득합니다"""
        return self.xing.GetErrorMessage(errcode)

    def is_load_api(self):
        """API Dll이 로드 되었는지 여부를 확인합니다"""
        return self.xing.IsLoadAPI()

    def get_server_name(self):
        """접속한 서버의 이름을 반환합니다"""
        return self.xing.GetServerName()


class Query:
    def __init__(self, instance, trcode):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        #com object 생성
        XAEvents.instance = instance #event class에 current instance를 넘김
        pythoncom.CoInitialize()
        client = win32com.client.DispatchEx("XA_DataSet.XAQuery")
        self.xing = win32com.client.DispatchWithEvents(client, XAEvents)
        #self.xing = win32com.client.DispatchWithEvents("XA_DataSet.XAQuery", XAEvents)
        self.xing.ResFileName = os.path.join(RES_DIR, trcode+'.res')

    def request(self, blockname, fields, bnext=False):
        """ 
        조회 TR을 요청 
        args:
            - blockanme : string
            - fields : 단일데이터 :{ fieldname : data }, 복수데이터: [{},{},..]
            - bnext : boolean (False : 조회, True: 다음 조회)
        returns: (0 이상: 성공, 0 미만: 실패)
        """

        if isinstance(fields, list):
            for i, obj in enumerate(fields):
                for key, val in obj.items():
                    self.set_field_data(blockname, key, val, i)
        elif isinstance(fields, dict):
            for key, val in fields.items():
                self.set_field_data(blockname, key, val)
        else:
            raise ValueError("Type of 'input value' is wrong: ", fields)

        return self.xing.Request(bnext)

    def is_next(self):
        """ 연속 조회 데이터가 있는지 확인"""
        return self.xing.IsNext

    def get_field_data(self, blockname, fieldname, index):
        """
        블록의 필드 데이터를 취득
        반환값: 블록의 필드 데이터
        """
        return self.xing.GetFieldData(blockname, fieldname, index)

    def set_field_data(self, blockname, fieldname, data, occurs=0):
        """
        블록의 필드 데이터를 설정
        """
        self.xing.SetFieldData(blockname, fieldname, occurs, data)

    def get_block_count(self, blockname):
        """
        블록이 occurs일 경우, occurs의 개수를 취득
        returns: occurs의 갯수
        """
        return self.xing.GetBlockCount(blockname)

    def set_block_count(self, blockname, cnt):
        """
        블록의 개수를 설정. Inblock의 경우에만 사용
        args:
            - blockname : string (블록명)
            - cnt : int (블록의 개수)
        """
        self.xing.SetBlockCount(blockname, cnt)

    def load_from_resfile(self, filename):
        """ 
        res 파일을 지정
        returns: (성공:True, 실패:False)
        """
        return self.xing.LoadFromResFile(filename)

    def clear_block_data(self, blockname):
        """ 지정한 블록의 내용을 삭제 """
        self.xing.ClearBlockData(blockname)

    def get_block_data(self, blockname):
        """ 
        블록의 전체 데이터를 취득 
        t3102(뉴스본문) TR을 이용하여 뉴스 정보 조회시 유용
        """
        return self.xing.GetBlockData(blockname)

    def get_tr_count_per_sec(self, trcode):
        """ TR의 초당 전송 가능 횟수 """
        return self.xing.GetTrCountPerSec(trcode)


    def request_service(self, code, data):
        """ 부가 서비스 TR을 요청 (성공:0, 실패: 0 미만)"""
        return self.xing.RequestService(code, data)

    def remove_service(self, code, data):
        """ 부가 서비스 TR 해제 """
        self.xing.RemoveService(code, data)

    def request_linkto_hts(self, linkname, data, filler=''):
        """API에서 hts 연동을 원할때 요청(성공: True, 실패: False) """
        self.xing.RequestLinkToHTS(linkname, data, filler)

    def decompress(self, blockname):
        """ 
        압축 데이터 수신이 가능한 TR의 압축 해제
        returns: 압축을 해제한 데이터의 길이
        """
        return self.xing.Decompress(blockname)

    def get_field_chart_real_data(self, blockname, fieldname):
        """
        차트 지표 실시간 데이터 수신시, 필드 데이터 값
        returns: 블록의 필드 데이터
        """
        return self.xing.GetFieldChartRealData(blockname, fieldname)

    def get_attribute(self, blockname, fieldname, attribute, occurs):
        """ attribute 정보를 취득 """
        return self.xing.GetAttribute(blockname, fieldname, attribute, occurs)
    
    def get_tr_count_base_sec(self, trcode):
        """ 
        tr의 초당 전송 가능 횟수(base)
        returns: Base 시간(초단위)
        """
        return self.xing.GetTRCountBaseSec(trcode)

    def get_tr_count_request(self, trcode):
        """
        10분내 요청한 TR의 횟수
        returns: 10분내 요청한 해당 tr의 총 횟수
        """
        return self.xing.GetTRCountRequest(trcode)


class Real:
    def __init__(self, instance, trcode):
        super().__init__()
        self.logger = logging.getLogger()

        #com object 생성
        XAEvents.instance = instance #event class에 current instance를 넘김
        
        pythoncom.CoInitialize()
        client = win32com.client.DispatchEx("XA_DataSet.XAQuery")
        self.real = win32com.client.DispatchWithEvents(client, XAEvents)
        
        #self.real = win32com.client.DispatchWithEvents("XA_DataSet.XAReal", XAEvents)
        self.real.ResFileName = os.path.join(RES_DIR, trcode+'.res')

    def advise_real_data(self):
        """ TR을 등록합니다"""
        self.real.AdviseRealData()
    
    def unadvise_real_data(self):
        """등록된 실시간 데이터를 해제합니다."""
        self.real.UnadviseRealData()

    def unadvise_real_data_with_key(self, code):
        """
        특정 종목의 수신을 해제합니다
        code(string) : 종목 코드
        """
        self.real.UnadviseRealDataWithKey(code)

    def get_field_data(self, blockname, fieldname):
        """
        블록의 필드 데이터를 취득합니다.
        blockname(string) : tr의 블록명
        fieldname(string) : 블록의 필드명
        """
        return self.real.GetFieldData(blockname, fieldname)

    def set_field_data(self, blockname, fieldname, value):
        """
        블록의 필드 데이터를 설정합니다.
        blockname(string) : tr의 블록명
        fieldname(string) : 블록의 필드명
        value (data): 데이터
        """
        self.real.SetFieldData(blockname, fieldname, value)


    def load_from_resfile(self, filename):
        """ 
        res 파일을 지정
        returns: (성공:True, 실패:False)
        """
        return self.real.LoadFromResFile(filename)

    def get_block_data(self, blockanme):
        """
        블록의 전체 데이터 값을 취득합니다.
        blockanme(string) : tr의 블록명
        returns : 블록의 전체 데이터
        """
        return self.real.GetBlockData(blockanme)

    