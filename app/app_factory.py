from fastapi import FastAPI
from app.router import route
from transfer_data.socketio_server import app as socket_app, origins
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from services_app.redis_client import RedisClient
from services_app.socketio_client import SocketIOClient


def create_app() -> FastAPI:
    """
    Creates and configures the FastAPI application instance.

    :return: FastAPI application instance.
    """
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=['*'],
            allow_headers=['*']
        )
    ]
    app = FastAPI(middleware=middleware)
    app.include_router(route)

    # Mount SocketIO application into FastAPI
    app.mount("/socket.io", socket_app)

    redis_client = RedisClient()
    socketio_client = SocketIOClient()

    @app.on_event("startup")
    async def startup_event():
        """
        Application startup event. Connect to Redis and Socket.IO.
        """
        await redis_client.connect()
        await socketio_client.connect()
        app.state.redis = redis_client.redis
        app.state.sio = socketio_client.sio

    @app.on_event("shutdown")
    async def shutdown_event():
        """
        Application shutdown event. Disconnect from Redis and Socket.IO.
        """
        await redis_client.disconnect()
        await socketio_client.disconnect()

    return app
