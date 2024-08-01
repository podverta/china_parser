import json
import uvicorn
from fastapi import FastAPI
from app.router import route
from transfer_data.socketio_server import app as socket_app, origins
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from config import create_redis_pool, AsyncBufferHandler, log_buffer, logger
import logging

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


@app.on_event("startup")
async def startup_event():
    app.state.redis = await create_redis_pool()
    app.state.buffer_handler = AsyncBufferHandler(log_buffer, app.state.redis)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    app.state.buffer_handler.setFormatter(formatter)
    logger.addHandler(app.state.buffer_handler)

@app.on_event("shutdown")
async def shutdown_event():
    app.state.redis.close()
    await app.state.redis.wait_closed()

app.include_router(route)

# Монтируем приложение SocketIO в FastAPI
app.mount("/socket.io", socket_app)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8123, reload=True)
