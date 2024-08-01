import json
from fastapi import FastAPI
from app.router import route
from transfer_data.socketio_server import app as socket_app, origins
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import uvicorn

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

# Монтируем приложение SocketIO в FastAPI
app.mount("/socket.io", socket_app)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8123, reload=True)
