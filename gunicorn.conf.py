# Gunicorn production configuration
# Usage: gunicorn -c gunicorn.conf.py wsgi:app

import multiprocessing

# Number of worker processes — 2-4 × CPU cores is the standard guideline.
# FinBERT loads a large model into memory; keep workers low to avoid OOM.
workers = min(2, multiprocessing.cpu_count())

# Use sync worker (FinBERT inference is CPU-bound, not I/O-bound)
worker_class = "sync"

# Binding
bind = "0.0.0.0:5001"

# Timeouts — analysis can take 30–60 s with FinBERT on CPU
timeout = 120
graceful_timeout = 30
keepalive = 5

# Logging
accesslog = "-"   # stdout
errorlog  = "-"   # stdout
loglevel  = "info"

# Reload on code change — disable in production
reload = False
