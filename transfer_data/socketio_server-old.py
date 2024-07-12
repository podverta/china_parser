import json
import socketio
from dotenv import load_dotenv
from app.logging import setup_logger

# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка логгера
logger = setup_logger('socketio', 'socketio_debug.log')



sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    # namespaces='/socket.io',
    # max_http_buffer_size=10 * 1024 * 1024  # 10 MB
)
app = socketio.ASGIApp(sio)

connected_clients = set()

async def send_to_logs(message: str):
    """
    Отправляет сообщение в логгер и выводит его в консоль.

    :param message: Сообщение для логгера.
    """
    logger.info(message)
    print(f"Logger: {message}")


@sio.on('connect')
async def connect(sid: str, environ: dict):
    """
    Обработчик события подключения клиента.

    :param sid: Идентификатор сессии клиента.
    :param environ: Среда окружения.
    """
    connected_clients.add(sid)
    await send_to_logs(f"Клиент подключился: {sid}")


@sio.on('disconnect')
async def disconnect(sid: str):
    """
    Обработчик события отключения клиента.

    :param sid: Идентификатор сессии клиента.
    """
    connected_clients.remove(sid)
    await send_to_logs(f"Клиент отключился: {sid}")

@sio.on('message')
async def message(sid: str, data: str):
    """
    Обработчик события получения сообщения от клиента.

    :param sid: Идентификатор сессии клиента.
    :param data: Данные, полученные от клиента.
    """
    await send_to_logs(f"Получено сообщение от {sid}: {data}")
    await sio.send(data)

async def broadcast(data: str):
    """
    Отправка данных всем подключенным клиентам.

    :param data: Данные для отправки.
    """
    await send_to_logs(f"Отправка данных {data} для {len(connected_clients)} клиентов")
    await sio.emit('message', data)

async def send_message(data: dict):
    """
    Отправка сообщения через Socket.IO.

    :param data: Данные для отправки.
    """
    await send_to_logs("Подготовка к отправке данных на Socket.IO сервер...")
    try:
        json_data = json.dumps(data)
        await sio.emit('message', json_data)
        await send_to_logs("Данные отправлены на Socket.IO сервер")
    except Exception as e:
        await send_to_logs(f'Ошибка при отправке данных: {str(e)}')