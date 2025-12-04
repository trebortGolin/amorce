# Gunicorn configuration file for MCP Wrapper production deployment

import multiprocessing

# Server socket
bind = "0.0.0.0:5001"

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"  # Can use 'gevent' for async if needed
worker_connections = 1000
timeout = 120
keepalive = 5

# Logging
loglevel = "info"
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "mcp-wrapper"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed for production)
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'

# Server hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    server.log.info("Starting MCP Wrapper with Gunicorn")

def on_reload(server):
    """Called to recycle workers during a reload."""
    server.log.info("Reloading MCP Wrapper")

def when_ready(server):
    """Called when the server is ready to serve requests."""
    server.log.info("MCP Wrapper is ready to serve requests")

def worker_int(worker):
    """Called when a worker receives the SIGINT or SIGQUIT signal."""
    worker.log.info("Worker received INT or QUIT signal")

def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal."""
    worker.log.info("Worker received SIGABRT signal")
