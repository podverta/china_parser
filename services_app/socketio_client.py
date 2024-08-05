import os
import socketio
from dotenv import load_dotenv
from app.logging import setup_logger


load_dotenv()
SOCKETIO_URL = os.getenv('SOCKETIO_URL')
SOCKET_KEY = os.getenv('SOCKET_KEY')

logger = setup_logger('socketio', 'socketio.log')

class SocketIOClient:
    def __init__(self):
        self.url = SOCKETIO_URL
        self.socket_key = SOCKET_KEY
        self.sio = socketio.AsyncClient()

    async def connect(self) -> None:
        """
        Establishes a connection to the Socket.IO server.
        """
        try:
            await self.sio.connect(self.url, auth={'socket_key': self.socket_key})
            logger.info(f"Connected to Socket.IO server at {self.url}")
        except Exception as e:
            logger.info(f"Failed to connect to Socket.IO server: {e}")
            raise

    async def disconnect(self) -> None:
        """
        Disconnects from the Socket.IO server.
        """
        try:
            await self.sio.disconnect()
            logger.info("Disconnected from Socket.IO server")
        except Exception as e:
            logger.info(f"Failed to disconnect from Socket.IO server: {e}")
            raise
