FROM python:3.7.4

COPY . /code

WORKDIR /code
RUN pip install -r requirements.txt
CMD gunicorn app:app --error-logfile gunicorn_error.log -b 0.0.0.0:8081 --thread 5