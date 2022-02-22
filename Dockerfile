FROM python:3.8-slim

WORKDIR /app

COPY ./requirements ./requirements

RUN pip install -r requirements/dev.txt

CMD ["gunicorn", "app:app()", "-c", "gunicorn.conf.py"]
