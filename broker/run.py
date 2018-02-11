import sys
import os
import logging
import time
import traceback
from datetime import date

import pythoncom
from channels import channel_layers, Channel

from workers import Broker, DBmanager
#from xingapi.meta import TR, Helper

sys.path.append('..\\website')
from carpediem.asgi import channel_layer

WORKERS = ['broker','dbmanager']
# websocket으로 보낸 action을 중개함


def run(worker):
    """
    웹으로부터 channel을 통해 요청을 받아 처리하는 함수
    두 종류의 worker가 존재하며 서로 다른 프로세서로 돌림
    broker: 시장 정보, 실시간 데이터, 주문 관리
    dbmanager: 거래 정보 다운로드 및 갱신
    """


    if worker == 'broker':
        ebest = Broker()
        logger = logging.getLogger()
    elif worker == 'dbmanager':
        ebest = DBmanager()

        #파일 로그 설정
        logger = logging.getLogger()
        logFormatter = logging.Formatter(
            "[%(asctime)s]%(message)s", datefmt="%m-%d %H:%M:%S")
        filename = date.strftime(date.today(), '%Y%m%d')
        fileHandler = logging.FileHandler("log/{0}.log".format(filename))
        fileHandler.setFormatter(logFormatter)
        logger.addHandler(fileHandler)

    while True:
        pythoncom.PumpWaitingMessages()
        (msgid, msg) = channel_layer.receive([worker], block=False)

        # 10초 이상 지난 요청은 pass
        if msg and (time.time() - msg.get('timestamp') > 10):
            continue

        if msgid == worker:
            logger.info("receive: %s", msg.get("method"))

            try:
                data = getattr(ebest, msg.get("method"))(**msg.get("args"))
                err = False

            except Exception as e:
                data = str(e)
                err = True
                print(traceback.format_exc())
                logger.warning(e)

            finally:
                if data is not None:
                    reply = dict(
                        worker=worker,
                        method=msg.get("method"),
                        data=data,
                        error=err
                    )
                    logger.debug("return: %s", reply)
                    Channel("web").send(reply)

        time.sleep(0.01)



if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s]%(message)s",
        datefmt="%m-%d %H:%M:%S"
    )

    if sys.argv[1] not in WORKERS:
        logging.info("\"%s\" is not worker", sys.argv[1]) 
    else:
        logging.info("\"%s\" program started",sys.argv[1])
        run(sys.argv[1])