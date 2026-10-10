# One worker owns the scheduler and collection jobs. Do not use --preload or replicas.
bind = '0.0.0.0:8000'
workers = 1
worker_class = 'gthread'
threads = 8
timeout = 120
graceful_timeout = 30
keepalive = 5
max_requests = 0
accesslog = None
errorlog = '-'
loglevel = 'warning'
worker_tmp_dir = '/tmp'
forwarded_allow_ips = '127.0.0.1,::1'
