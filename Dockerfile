FROM python:alpine

WORKDIR /app

COPY ./requirements/prod.txt ./requirements.txt

RUN apk add --update --no-cache g++ gcc libxslt-dev

RUN pip install -r requirements.txt

CMD gunicorn app:app -c gunicorn.conf.py
