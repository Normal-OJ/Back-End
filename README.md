# NOJ Backend

[![Coverage Badge](https://normal-oj.github.io/Back-End/coverage.svg)](https://normal-oj.github.io/Back-End/index.html)

## Setup Instructions for running Back-End tests locally

Before starting, you need to have Python installed with a version >= 3.11.

### 1. Install Poetry

Follow the official Poetry installation guide: [https://python-poetry.org/docs/](https://python-poetry.org/docs/)

### 2. Install Dependencies

Run the following command to install all dependencies:
```bash
poetry install
```

Poetry makes [project environment isolation](https://python-poetry.org/docs/managing-environments/) one of its core features.

### 3. Run Tests

To ensure everything is set up correctly, run the tests:
```bash
poetry run pytest
```
All tests should pass (or skip). Create an issue if you found any tests failed.

### 5. Code Formatting

To format the codebase using `yapf`, run the following command:
```bash
poetry run yapf -ir .
```

### 6. Pre-Commit Hooks

To ensure code quality and consistency, set up pre-commit hooks:

Install pre-commit:
```bash
poetry run pre-commit install
```

This will set up pre-commit hooks that will run some checks automatically before each commit.

## Set Environment Variables for running NOJ

To run NOJ (see the README of the root project), configure the following environment variables in `docker-compose.yml` before `docker compose up`:

### MinIO Configuration

Without [MinIO](https://min.io/), you cannot create Problems and Submissions.

We have set up the default values of these four variables in `docker-compose.override.yml`, if you need to develop locally with MinIO, make sure to configure them properly [based on the README in NOJ root project](https://github.com/Normal-OJ/Normal-OJ/blob/master/README.md#setup-minio). You can skip this if you will not develop features related to Problems and Submissions.

- `MINIO_HOST`: The host for the MinIO server.
- `MINIO_ACCESS_KEY`: The access key for MinIO.
- `MINIO_SECRET_KEY`: The secret key for MinIO.
- `MINIO_BUCKET`: The bucket name used in MinIO.

### SMTP Configuration

SMTP server is required for sending emails, such as password reset and signup new account. You can skip this if you will not develop features related to them.

- `SMTP_SERVER`: SMTP server
- `SMTP_NOREPLY`: email account used to send emails, e.g. `noreply@noj.tw`
- `SMTP_NOREPLY_PASSWORD`: password of `SMTP_NOREPLY` (optional)

### Optional

These variables have default values, you can skip them if you want to use the default values.

- `MONGO_HOST`: host to MongoDB, used by `mongoengine.connect`
- `REDIS_HOST` / `REDIS_PORT`: host and port to Redis
- `JWT_EXP`: JWT expiration in days
- `JWT_ISS`: JWT issuer, e.g. `noj.tw`
- `JWT_SECRET`: JWT secret, ensure that you set a strong enough value in production
- `SERVER_NAME`: hostname used in external link (without schema), e.g. `api.noj.tw`
- `APPLICATION_ROOT`: the path that flask app is mounted, also used to generate external link, e.g. `/api`. default to `/`
