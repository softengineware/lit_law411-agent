"""Celery application configuration for lit_law411-agent."""

from celery import Celery

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

# Create Celery app
celery_app = Celery(
    "lit_law411_agent",
    broker=settings.get_redis_url(),
    backend=settings.get_redis_url(),
    include=[
        "src.workers.tasks",
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task routing
    task_routes={
        "src.workers.tasks.process_content": {"queue": "content_processing"},
        "src.workers.tasks.extract_transcription": {"queue": "transcription"},
        "src.workers.tasks.generate_embeddings": {"queue": "embeddings"},
        "src.workers.tasks.scrape_content": {"queue": "scraping"},
        "src.workers.tasks.periodic_cleanup": {"queue": "maintenance"},
    },
    
    # Task execution
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task results
    result_expires=3600,  # 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
    },
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    
    # Task time limits
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,       # 10 minutes hard limit
    
    # Retry configuration
    task_default_retry_delay=60,    # 1 minute
    task_max_retries=3,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Beat schedule (for periodic tasks)
    beat_schedule={
        "cleanup-expired-cache": {
            "task": "src.workers.tasks.periodic_cleanup",
            "schedule": 3600.0,  # Every hour
            "options": {"queue": "maintenance"},
        },
        "health-check": {
            "task": "src.workers.tasks.health_check",
            "schedule": 300.0,   # Every 5 minutes
            "options": {"queue": "maintenance"},
        },
        "sync-databases": {
            "task": "src.workers.tasks.sync_databases", 
            "schedule": 1800.0,  # Every 30 minutes
            "options": {"queue": "maintenance"},
        },
    },
    
    # Redis-specific settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    
    # Task compression
    task_compression="gzip",
    result_compression="gzip",
    
    # Security
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
)

# Configure logging
celery_app.conf.update(
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Set up periodic tasks."""
    logger.info("Celery periodic tasks configured")


@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    logger.info(f"Request: {self.request!r}")
    return f"Debug task executed: {self.request.id}"


# Health check task
@celery_app.task(name="health_check")
def health_check():
    """Health check task to verify worker connectivity."""
    import time
    start_time = time.time()
    
    # Simulate some work
    time.sleep(0.1)
    
    execution_time = time.time() - start_time
    
    logger.info("Health check completed", execution_time=execution_time)
    return {
        "status": "healthy",
        "execution_time": execution_time,
        "worker_id": celery_app.current_worker_task.request.hostname if hasattr(celery_app, 'current_worker_task') else "unknown"
    }


# Task failure handler
@celery_app.task(bind=True, max_retries=3)
def safe_task_wrapper(self, task_name: str, *args, **kwargs):
    """
    Wrapper for tasks that need safe execution with retries.
    
    Args:
        task_name: Name of the task to execute
        *args: Arguments to pass to the task
        **kwargs: Keyword arguments to pass to the task
    """
    try:
        # Import and execute the actual task
        task_module = __import__(f"src.workers.tasks", fromlist=[task_name])
        task_func = getattr(task_module, task_name)
        
        result = task_func(*args, **kwargs)
        logger.info("Task completed successfully", task=task_name, result=result)
        return result
        
    except Exception as exc:
        logger.error(
            "Task failed",
            task=task_name,
            attempt=self.request.retries + 1,
            max_retries=self.max_retries,
            error=str(exc)
        )
        
        if self.request.retries < self.max_retries:
            # Exponential backoff
            countdown = 2 ** self.request.retries
            logger.info(f"Retrying task in {countdown} seconds", task=task_name)
            
            raise self.retry(countdown=countdown, exc=exc)
        else:
            logger.error("Task failed permanently", task=task_name, error=str(exc))
            raise


# Custom task base class
class LoggingTask(celery_app.Task):
    """Base task class with logging support."""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called on task success."""
        logger.info(
            "Task succeeded",
            task_id=task_id,
            task_name=self.name,
            result=retval
        )
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called on task failure."""
        logger.error(
            "Task failed",
            task_id=task_id,
            task_name=self.name,
            error=str(exc),
            traceback=str(einfo)
        )
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called on task retry."""
        logger.warning(
            "Task retry",
            task_id=task_id,
            task_name=self.name,
            error=str(exc),
            attempt=self.request.retries + 1
        )


# Set default task class
celery_app.Task = LoggingTask


if __name__ == "__main__":
    celery_app.start()