import serial
import time
import sys
import re
import threading
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout,
                             QPushButton, QLabel,
                               QTextEdit,  QCheckBox)
from PySide6.QtCore import  Signal,  QObject

#class 구성: seral 통신부 / GUI 연동부: serial Class를 만들어서 데이터를 읽어온 후에
#TraceBoard업데이트를 한다면 메인 스레드인 GUI가 멈추지 않고 시리얼 데이터를 실시간으로 (송)수신
#데이터 보존을 위해서 GUI 업데이트를 할 때 별도의 스레드를 오픈해도 안전하게 UI변경

#QLabel을 통해 배치를 맞게하는 건 보너스
#추후 개선점: 로그파일 저장
#GUI에서 이제 시리얼 여러 포트 사용 가능
#버튼으로 데이터 전송(b'Command')

# 개선점: 기존의 1초마다 불필요한 데이터 요청이 사라짐-> CPU & Serial 부하 감소 아 근데 걍 올릴거임
# 버튼을 눌렀을 때만 요청하기에 조금 더 직관적임
# 기존의 숫자값 좀 더 정확히

#mem_wrtie 로 실제 시간 보내는거 추가 T14:15 6bit 보낸단 말야 (14:)15:00으로 출력
#근데 얘가 뭐 건들게 있었던가
class SerialWorker(QObject):
    data_received = Signal(str,str)

    #__init__ : 얘도 콜백함수로 볼 수 있다
    def __init__(self, port="COM12", baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = True
        self.ser = None  # 'ser'을 None으로 초기화
        self.command_queue = []  # 명령 대기열 추가
        self.lock = threading.Lock()  # 무조건 실행

    def open_serial(self):
        """여기서 시리얼포트 열림"""
        if self.ser is None or not self.ser.is_open:
            try:
                self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
                print(f"시리얼 포트 {self.port} 연결됨.")
                return True
            except serial.SerialException as e:
                print(f"시리얼 포트 접근 불가: {e}")
                self.ser = None
                return False

    def close_serial(self):
        """시리얼 포트 닫기"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("시리얼 포트 닫힘")

    def run(self):
        if not self.open_serial():
            print("시리얼 포트를 열 수 없습니다.")
            return
        try:    #dev/ttySAC0 .. 1.. 2.. 3
            print("시리얼 포트 오픈: COM12")
            while self.running:
                current_time = datetime.now().strftime("T%H:%M")
                self.ser.write(current_time.encode())  # 시간 전송
                print(repr(current_time.encode()))  # 실제 전송 데이터 확인
                print(f"[현재시각: {current_time[1:]}]")
                # 대기열에 명령이 있으면 처리
                with self.lock:
                    if self.command_queue:
                        command = self.command_queue.pop(0)
                        print(f"명령 전송: {command}")
                        self.ser.write(str(command).encode())
                        print(repr(command.encode()))


                data = self.ser.readline().decode('utf-8').strip()
                print(f"[수신 데이터] {data}")


                adc_value = data.split()

                if len(adc_value) > 300:
                    adc_value = adc_value[1]    #두번째 부터 그리고 300이하 쓰레기 무시
                    print(f"ADC Value: {adc_value}")
                else:
                    adc_value = "N/A"


                #UI업데이트신호부
                self.data_received.emit(current_time, adc_value)

                #기존에 re모듈로 데이터 파싱하던거

                # sw_state, adc_value = "N/A", "N/A"
                # # RE module
                # match_sw = re.search(r"SW\s(\d+)", data)
                # match_adc = re.search(r"ADC\s*:\s*(\d+)", data)
                # if match_sw:
                #     sw_state = match_sw.group(1)
                # if match_adc:
                #     adc_value = match_adc.group(1)
                #
                # # 숫자는 encode() 해줘도 되고 문자는 string.encode()해야됨
                # print(f"SW: {sw_state}, ADC: {adc_value}")
                #



                #나중에 버튼 제어 추가
                time.sleep(1)

        except serial.SerialException as e:
            print(f"시리얼 오류 발생: {e}")
        finally :
                self.ser.close()



    def send_command(self, command):
            # self.open_serial()
            with self.lock:
                self.command_queue.append(command)
                print(f"명령 대기열 추가: {command}")
            self.ser.write(str(command).encode())
            print(f"\n<실제로 STM32로 보낸 명령어: {command}> \n")
            print(repr(command.encode()))  # 실제 전송 데이터 확인

    def send_adc(self):
        self.send_command('R00001')

    def send_timer(self):
        self.send_command('R00002')

    def send_buzzer(self):
        self.send_command('R00003')

    def send_reset(self):
        self.send_command('R00004')

    def send_time(self):
        self.send_command('R00005')




# GUI 처리부
class TraceBoard(QWidget):
    def __init__(self, serial_worker):
        super().__init__()
        self.setWindowTitle("Real-Time Data Display")
        layout = QVBoxLayout()

        # 외부에서 전달받은 serial_worker로
        self.serial_worker = serial_worker


        # 실시간 로그 텍스트 박스
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True) #ReadOnly
        layout.addWidget(self.text_edit)

        # 각각의 데이터 표시 라벨
        self.timer_label = QLabel("Timer: ")
        self.time_label = QLabel("Time: ")
        self.adc_label = QLabel("ADC Value: ")

        layout.addWidget(self.timer_label)
        layout.addWidget(self.time_label)
        layout.addWidget(self.adc_label)

        # PushButton
        # 이 안에 리버스 기능을 넣음
        self.adc = QPushButton('ADC Value')
        self.adc.clicked.connect(self.on_adc_clicked)


        self.timer = QPushButton('Timer')
        self.timer.clicked.connect(self.on_timer_clicked)

        self.buzzer = QPushButton('RealTime')
        self.buzzer.clicked.connect(self.on_buzzer_clicked)

        self.time = QPushButton('time')
        self.time.clicked.connect(self.on_time_clicked)

        self.reset = QPushButton('reset')
        self.reset.clicked.connect(self.on_reset_clicked)



        self.power = QCheckBox('OFF')
        self.timer.setCheckable(True)
        self.power.clicked.connect(self.close)


        # 데이터 요청부 시작
        layout.addWidget(self.adc)
        layout.addWidget(self.timer)
        layout.addWidget(self.buzzer)
        layout.addWidget(self.reset)
        layout.addWidget(self.time)

        layout.addWidget(self.power)

        self.setLayout(layout)

    def on_adc_clicked(self):
        self.text_edit.append("ADC 값 요청 버튼 클릭됨")
        self.serial_worker.send_adc()


    def on_timer_clicked(self):
        self.text_edit.append("타이머 제어 버튼 클릭됨")
        self.serial_worker.send_timer()

    def on_buzzer_clicked(self):
        self.text_edit.append("부저 제어 버튼 클릭됨")
        self.serial_worker.send_buzzer()

    def on_time_clicked(self):
        self.text_edit.append("time 제어 버튼 클릭됨")
        self.serial_worker.send_time()

    def on_reset_clicked(self):
        self.text_edit.append("reset 제어 버튼 클릭됨")
        self.serial_worker.send_reset()
    #[1:]를 하면 하나 뺄 수 있네
    def update_ui(self, current_time, adc_value):
        # 로그 추가
        self.text_edit.append(f"[현재 시간: {current_time[1:]}] , ADC 값: {adc_value}")
        # 개별 데이터 업데이트
        self.timer_label.setText(f"타이머: {current_time[1:]}")
        self.time_label.setText(f"시간: {current_time[1:]}")
        self.adc_label.setText(f"ADC 값: {adc_value}")



#동시다발적 데이터 처리를 위한 threading System
def main():
    app = QApplication(sys.argv)

    # SerialWorker 인스턴스 하나만 생성
    serial_worker = SerialWorker()

    # TraceBoard에 serial_worker 전달
    window = TraceBoard(serial_worker)

    # 시그널 연결
    serial_worker.data_received.connect(window.update_ui)

    # 별도 스레드에서 SerialWorker 실행
    serial_thread = threading.Thread(target=serial_worker.run, daemon=True)
    serial_thread.start()

    window.show()
    try:
        app.exec()
    finally:
        serial_worker.stop()
        serial_thread.join(timeout=1)

if __name__ == '__main__':
    main()

