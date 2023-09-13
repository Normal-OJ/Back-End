# NOJ Backend

[![Coverage Badge](https://normal-oj.github.io/Back-End/coverage.svg)](https://normal-oj.github.io/Back-End/index.html)

This respository uses [Poetry](https://python-poetry.org/) to manage Python dependencies.

You need to have a Python interpreter higher than 3.8

## Config

These environment variables are used for config NOJ backend:

- `MONGO_HOST`: host to MongoDB, used by `mongoengine.connect`
- `REDIS_HOST` / `REDIS_PORT`: host and port to Redis
- `JWT_EXP`: JWT expiration in days
- `JWT_ISS`: JWT issuer, e.g. `noj.tw`
- `JWT_SECRET`: JWT secret, ensure that you set a strong enough value in production
- `SMTP_SERVER`: SMTP server
- `SMTP_NOREPLY`: email account used to send emails, e.g. `noreply@noj.tw`
- `SMTP_NOREPLY_PASSWORD`: password of `SMTP_NOREPLY` (optional)
- `SERVER_NAME`: hostname used in external link (without schema), e.g. `api.noj.tw`
- `APPLICATION_ROOT`: the path that flask app is mounted, also used to generate external link, e.g. `/api`. default to `/`
