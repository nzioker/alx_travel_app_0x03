import os
from celery import Celery

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alx_travel_app.settings')

app = Celery('alx_travel_app')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    """Debug task to verify Celery is working"""
    print(f'Request: {self.request!r}')
    return {'status': 'success', 'message': 'Celery is working!'}

# Optional: Configure task routes
app.conf.task_routes = {
    'listings.tasks.*': {'queue': 'emails'},
    'listings.tasks.cleanup_*': {'queue': 'maintenance'},
}

# Optional: Task priorities
app.conf.task_annotations = {
    'listings.tasks.send_booking_confirmation_email': {'rate_limit': '10/m'},
}
