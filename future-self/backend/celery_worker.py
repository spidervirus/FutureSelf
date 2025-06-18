import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Redis URL from environment or use default
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Create Celery instance
celery_app = Celery(
    "future_self",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"]
)

# Optional: Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    worker_max_tasks_per_child=200,
    broker_connection_retry_on_startup=True,
)

# This allows you to run this file directly to start a worker
if __name__ == "__main__":
    celery_app.start()