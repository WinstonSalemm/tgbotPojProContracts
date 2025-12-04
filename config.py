import os

API_TOKEN = os.getenv("7245964747:AAGbYsL_3--NZRh-rhTWsLX7aLELIvbZvjw")
API_ENDPOINT = os.getenv(
    "API_ENDPOINT",
    "http://localhost:5016/agreements/generate"  # дефолт, пока API локально
)
