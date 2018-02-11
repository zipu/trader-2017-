#######################################################
## XingAPI로 부터 시장 데이터를 수신하는 콘솔용 스크립트 ##
#######################################################
import sys
import os
import logging
import time
import traceback
from datetime import date
import pythoncom

from workers import DBmanager

TASKS = ['products', 'ohlc', 'density', 'backup']

def start(tasks):

    worker = DBmanager()
    worker.tasks = tasks
    worker.work()
    while True:
        pythoncom.PumpWaitingMessages()
        
        #while worker.messages:
        #    print(worker.messages.pop())



        time.sleep(0.01)



if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s][%(levelname)s]%(message)s",
        datefmt="%m-%d %H:%M:%S"
    )

    #파일 로그 설정
    logger = logging.getLogger()
    logFormatter = logging.Formatter(
        "[%(asctime)s]%(message)s", datefmt="%m-%d %H:%M:%S")
    filename = date.strftime(date.today(), '%Y%m%d')
    fileHandler = logging.FileHandler("log/{0}.log".format(filename))
    fileHandler.setFormatter(logFormatter)
    logger.addHandler(fileHandler)

    #프로세스 시작
    logging.info("DBmanager script started")
    
    arg = sys.argv[1]
    
    if arg.lower() == 'all':
        start(TASKS)
    elif arg in TASKS:
        start([arg])