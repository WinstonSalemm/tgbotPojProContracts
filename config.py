import os

API_TOKEN = os.getenv("BOT_TOKEN")
API_ENDPOINT = os.getenv(
    "API_ENDPOINT",
    "http://localhost:5016/agreements/generate"  # дефолт, пока API локально
)