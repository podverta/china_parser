import os
import socketio
from dotenv import load_dotenv

load_dotenv()
SOCKETIO_URL = os.getenv('SOCKETIO_URL')
SOCKET_KEY = os.getenv('SOCKET_KEY')


class SocketIOClient:
    def __init__(self):
        self.url = SOCKETIO_URL
        self.socket_key = SOCKET_KEY
        self.sio = socketio.AsyncClient()

    async def connect(self) -> None:
        """
        Устанавливает соединение с сервером Socket.IO.
        """
        try:
            await self.sio.connect(self.url, auth={'socket_key': self.socket_key})
            print(f"Connected to Socket.IO server at {self.url}")
        except Exception as e:
            print(f"Failed to connect to Socket.IO server: {e}")
            raise

    async def disconnect(self) -> None:
        """
        Закрывает соединение с сервером Socket.IO.
        """
        try:
            await self.sio.disconnect()
            print("Disconnected from Socket.IO server")
        except Exception as e:
            print(f"Failed to disconnect from Socket.IO server: {e}")
            raise
