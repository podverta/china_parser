from fastapi import FastAPI
from app.router import route
from transfer_data.socketio_server import app as socket_app
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

origins = [
    "http://10.10.10.34:8081",
    "http://127.0.0.1",
    "http://0.0.0.0",
    "http://localhost",
    "http://parserbk.compas-pro.ru",
    "https://parserbk.compas-pro.ru",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# @app.get("/")
# async def home():
#     return "Добро пожаловать на наш проект по парсеру"

app.include_router(route)

# Монтируем приложение SocketIO в FastAPI
app.mount("/socket.io", socket_app)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8123, reload=True)
