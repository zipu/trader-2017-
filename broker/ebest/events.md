# OnRecieveData : 서버로부터 데이터를 수신했을 때 발생
  * Args:
    - trcode: tr명

# OnReceiveMessage 서버로부터 메시지를 수신했을 때 발생
  * Args:
    - systemerror: TRUE면시스템오류, FALSE면그외오류
    - msgcode: 메시지코드
               TR Code가10자리인TR에한해서에러코드의범위는다음과같습니다.
               > 0000~0999 : 정상(ex ) 0040 : 매수주문이완료되었습니다.)
               > 1000~7999 : 업무오류메시지(1584 : 매도잔고가부족합니다.)
               > 8000~9999 : 시스템에러메시지
    - msg: 메시지
  

# ReceiveChartRealData: 차트지표데이터조회시, 실시간자동등록을“1”로했을경우
  * Args: 
    - trcode: tr명

# ReceiveRealData: 서버로부터 데이터를 수신 했을때 발생
  * Args: 
    - trcode: tr명


  