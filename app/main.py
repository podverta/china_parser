import uvicorn
from app.app_factory import create_app  # Import the application creation function

app = create_app()  # Create the FastAPI application

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8123, reload=True)
