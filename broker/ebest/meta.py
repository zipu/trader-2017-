import inspect
import base64
from collections import namedtuple
from Crypto.Cipher import XOR


class TR:

    #해외선물 종목 마스터 (o3101)
    class o3101:
        """ 종목 마스터"""
        CODE = 'o3101'
        INBLOCK = 'o3101InBlock'
        OUTBLOCK = 'o3101OutBlock'
        OCCURS = True
        TR_PER_SEC = 1

        def __init__(self):
            # caller 함수의 이름을 인스턴스 name에 저장
            # event 처리 함수내에서 name이 다르면 pass하는 용도 
            self.name = inspect.stack()[1][3]

    #해외선물 분봉조회
    class o3103:
        """분봉 데이터"""
        CODE = 'o3103'
        INBLOCK = 'o3103InBlock'
        OUTBLOCK = 'o3103OutBlock'
        OUTBLOCK1 = 'o3103OutBlock1'
        OCCURS = True
        TR_PER_SEC = 1

        def __init__(self):
            self.name = inspect.stack()[1][3]
    
    #해외선물 일별 (o3104)
    class o3104:
        """ 일별 데이터 """
        CODE = 'o3104'
        INBLOCK = 'o3104InBlock'
        OUTBLOCK = 'o3104OutBlock1'
        OCCURS = True
        TR_PER_SEC = 1

        def __init__(self):
            self.name = inspect.stack()[1][3]
    
    #해외선물 종목 정보 (o3105)
    class o3105:
        """ 종목 마스터 """
        CODE = 'o3105'
        INBLOCK = 'o3105InBlock'
        OUTBLOCK = 'o3105OutBlock'
        OCCURS = False
        TR_PER_SEC = 1

        def __init__(self):
            self.name = inspect.stack()[1][3]

    #해외선물 관심 (o3107)
    class o3107:
        """ 관심 """
        CODE = 'o3107'
        INBLOCK = 'o3107InBlock'
        OUTBLOCK = 'o3107OutBlock'
        OCCURS = True
        TR_PER_SEC = 1

        def __init__(self):
            self.name = inspect.stack()[1][3]
    
    #해외선물 차트 일주월 (o3108)
    class o3108:
        """차트 (일주월)"""
        CODE = 'o3108'
        INBLOCK = 'o3108InBlock'
        OUTBLOCK = 'o3108OutBlock'
        OUTBLOCK1 = 'o3108OutBlock1'
        OCCURS = True
        TR_PER_SEC = 1

        def __init__(self):
            self.name = inspect.stack()[1][3]


    #해외선물 체결 (OVC)
    class OVC:
        """체결 """
        CODE = 'OVC'
        INBLOCK = 'InBlock'
        OUTBLOCK = 'OutBlock'
        OCCURS = False
        TR_PER_SEC = 0

        def __init__(self):
            self.name = inspect.stack()[1][3]



class Helper:

    @staticmethod
    def classify_group(product):
        """
        시장 구분
        Grain(곡물)
        Metals(금속)
        Meats(육류)
        Energy(에너지)
        Tropical(과일)
        Rates(금리)
        Equities(지수)
        Fibers(섬유)
        Currencies(통화)
        """
        pass



    @staticmethod
    def market_symbol(gubun):
        if gubun == '001':
            return 'IDX'
        elif gubun == '002':
            return 'CUR'
        elif gubun == '003':
            return 'INT'
        elif gubun == '004':
            return "CMD"
        elif gubun == '005' or gubun == '006':
            return "MTL"
        elif gubun == '007':
            return "ENG"
    
    @staticmethod
    def get_month(gubun):
        if gubun == 'F':
            return 1
        elif gubun == 'G':
            return 2
        elif gubun == 'H':
            return 3
        elif gubun == 'J':
            return 4
        elif gubun == 'K':
            return 5
        elif gubun == 'M':
            return 6
        elif gubun == 'N':
            return 7
        elif gubun == 'Q':
            return 8
        elif gubun == 'U':
            return 9
        elif gubun == 'V':
            return 10
        elif gubun == 'X':
            return 11
        elif gubun == 'Z':
            return 12

    @staticmethod
    def decrypt(key, ciphertext):
      cipher = XOR.new(key)
      return cipher.decrypt(base64.b64decode(ciphertext))

    @staticmethod
    def symbols_from_code(products, code):
        for market, val in products.items():
            for group, val2 in val.items():
                if isinstance(val2, dict): # actives같이 리스트 형태 아이템 제외
                    if code in val2.keys():
                        return (market, group)

    @staticmethod
    def comp_month(item1, item2):
        """ 액티브 월물 및 근월물 계산할 때 사용
            item1 이 item2보다 빠르거나 같으면 item1, 느리면 item2 리턴
        """
        if len(item1[1]) != len(item2[1]):
            raise ValueError("size of two lists are NOT same")

        if item1[1] == item2[1]: # 두 리스트가 같으면 0 리턴
            return item1

        elif int(item1[1][0]) < int(item2[1][0]):
            return item1
        elif int(item1[1][0]) == int(item2[1][0]) and int(item1[1][1]) < int(item2[1][1]):
            return item1
        else:
            return item2
