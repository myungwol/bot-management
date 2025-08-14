# keep_alive.py

from flask import Flask
from threading import Thread

# #메세지: Flask 웹 서버 애플리케이션을 생성합니다.
app = Flask('')


@app.route('/')
def home():
    return "봇이 활성화되었습니다."


def run():
    # #메세지: Flask 웹 서버를 시작합니다.
    # #메세지: host='0.0.0.0'은 Replit 환경에서 외부 접속을 허용하기 위한 설정입니다.
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    # #메세지: 웹 서버를 실행하는 'run' 함수를 별도의 스레드(백그라운드 작업)에서 실행하도록 설정합니다.
    # #메세지: 이렇게 해야 웹 서버가 돌아가는 동안에도 디스코드 봇이 멈추지 않고 계속 작동할 수 있습니다.
    t = Thread(target=run)
    t.start()
