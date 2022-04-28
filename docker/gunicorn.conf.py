import multiprocessing
import os
import logging


logger = logging.getLogger('inventree')

workers = os.environ.get('INVENTREE_GUNICORN_WORKERS', None)

if workers is not None:
    try:
        workers = int(workers)
    except ValueError:
        workers = None

if workers is None:
    workers = multiprocessing.cpu_count() * 2 + 1

logger.info(f"Starting gunicorn server with {workers} workers")

max_requests = 1000
max_requests_jitter = 50
