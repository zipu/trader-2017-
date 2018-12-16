from datetime import datetime, date, timedelta
from channels import Channel
from channels.log import setup_logger
from trading.models import Product, Code, Equity, Account, Entry, Exit

logger = setup_logger(__name__)
COMISSION = 7 #수수료

class post:
    @staticmethod
    def save(products):
        """ broker에서 넘어온 시장정보를 db에 업데이트"""
        for group in products.values():

            #상품정보 업데이트
            product, created = Product.objects.update_or_create(
                pk=group['group'],
                defaults={
                    'name': group['name'],
                    'group': group['group'],
                    'market': group['market'],
                    'currency': group['currency'],
                    'open_margin': group['open_margin'],
                    'keep_margin': group['keep_margin'],
                    'open_time': datetime.strptime(group['open_time'], '%H%M%S').time(),
                    'close_time': datetime.strptime(group['close_time'], '%H%M%S').time(),
                    'tick_unit': group['tick_unit'],
                    'tick_value': group['tick_value'],
                    'commission': COMISSION,
                    'notation': group['notation'],
                    'decimal_places': group['decimal_places'],
                    'last_update': datetime.strptime(group['last_update'], '%Y%m%d%H%M'),
                    'front': group['front']
                }
            )

            # 액티브 월물 설정 (액티브 월물, 날짜, 가격갭)
            # case 1. 새로운 상품인 경우
            #  ( 근월물, 어제, 0 )
            # case 2. 월물이 한개이고 액티브 월물 변경안된 경우: 비교 안함
            # case 3. 기존 액티브 월물이 차월물인 경우: 비교 안함
            # case 4. 기존 액티브 월물과 같은 경우: 변경 안함
            # case 5. 액티브 웜물이 변경된 경우
            #    (1) 액티브 월물 변경
            #    (2) 액티브 날짜 --> 데이터 업데이트 날짜
            #    (3) 가격갭 변경
            # case 6. 액티브 월물이 존재하지 않는경우 : pass
            # cast 7. 변경된 액티브 월물이 기존보다 앞선 월물인경우: pass

            #case 1

            if 'active' not in group:
                pass

            elif created:
                product.active = group['active']
                product.activated_date = datetime.strptime(group['activated_date'], '%Y%m%d').date()
                product.price_gap = 0
            else:
                if product.active != group['active']:
                    #case 7
                    if Code.objects.get(pk=group['active']).month \
                        <= Code.objects.get(pk=product.active).month:
                        pass

                    #case 5
                    else:
                        last_price = Code.objects.get(pk=product.active).ec_price
                        active_price = Code.objects.get(pk=group['active']).ec_price
                        price_gap = active_price - last_price

                        msg = "(%s) active month changed: %s --> %s (price gap: %s at %s)"%\
                               (product.name, product.active, group['active'], price_gap, group['activated_date'])
                        logger.info(msg)
                        Channel("web").send({
                            "method": "log",
                            "data": msg
                        })

                        product.active = group['active']
                        product.activated_date = \
                            datetime.strptime(group['activated_date'], '%Y%m%d').date()
                        product.price_gap = price_gap

                #case 2
                elif 'front_codes' not in group:
                    pass

                #case 3
                elif product.active == group['front_codes'][1]['code']:
                    pass
                #case 4
                elif product.active == group['active']:
                    pass
            product.save()

            # 코드 업데이트
            for code in group['codes']:
                code['month'] = datetime.strptime(code['month'], "%Y%m").date()
                Code.objects.update_or_create(
                    pk=code['code'],
                    defaults={
                        'code': code['code'],
                        'product': product,
                        'month': code['month'],
                        'ec_price': code['ec_price']
                    }
                )

        msg = "** Market information update completed **"
        logger.info(msg)
        Channel("web").send({
            "method": "log",
            "data": msg
        })

        # Equity DB 업데이트
        yesterday = date.today() - timedelta(1)
        try:
            equity = Equity.objects.get(date=yesterday)
        except Equity.DoesNotExist:
            equity = Equity(date=yesterday)
        equity.update_equity()

    @staticmethod
    def get_active():
        """
        매매 데이터 업데이트용 기초정보 :
        group = {
             active: 액티브 월물,
             activated_date: 액티브 날짜,
             open_time: 장시작시간,
        """
        products = Product.objects.all()\
                   .values_list('group', 'name', 'active', 'activated_date',\
                                'price_gap', 'decimal_places', 'tick_unit')
        active = []
        
        for item in products:
            active.append({
                'group': item[0],
                'name': item[1],
                'active':item[2],
                'activated_date':item[3].strftime("%Y%m%d"),
                'price_gap': float(item[4]),
                'decimal_places': item[5],
                'tick_unit': float(item[6])
            })

        return active