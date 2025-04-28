bind = '0.0.0.0:8080'
errorlog = 'gunicorn_error.log'
loglevel = 'debug'
workers = 12
threads = 12
worker_class = 'gthread'
