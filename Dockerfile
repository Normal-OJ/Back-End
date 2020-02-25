FROM python:alpine

WORKDIR /app

COPY ./requirements.txt ./requirements.txt

RUN apk add --update --no-cache g++ gcc libxslt-dev

RUN pip install -r requirements.txt

RUN addgroup -S --gid 1000 normal-oj && \
    adduser -S --uid 1000 normal-oj normal-oj

USER normal-oj

CMD gunicorn app:app --error-logfile gunicorn_error.log -b 0.0.0.0:8080 --thread 5
