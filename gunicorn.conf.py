bind = '0.0.0.0:8080'
errorlog = 'gunicorn_error.log'

thread = 5
worker_class = 'gthread'
