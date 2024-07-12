import socketio

sio = socketio.Client()

@sio.event
def connect():
    print("Соединение установлено")

@sio.event
def disconnect():
    print("Соединение разорвано")

@sio.event
def message(data):
    print(f"Получено сообщение: {data}")

sio.connect('http://localhost:8123')
sio.wait()
