import logging
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from config import settings
from model import *
from mongo import *


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.Client(timeout=httpx.Timeout(5.0, read=30.0))
    yield
    app.state.http_client.close()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    from model.utils.response import NOJException

    @app.exception_handler(NOJException)
    async def noj_exception_handler(request: Request, exc: NOJException):
        return JSONResponse(
            {
                'status': 'err',
                'message': exc.message,
                'data': exc.data,
            },
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request,
                                           exc: RequestValidationError):
        return JSONResponse(
            {
                'status': 'err',
                'message': 'Invalid request body',
                'data': jsonable_encoder(exc.errors()),
            },
            status_code=400,
        )

    app.include_router(auth_router, prefix='/auth')
    app.include_router(profile_router, prefix='/profile')
    app.include_router(problem_router, prefix='/problem')
    app.include_router(submission_router, prefix='/submission')
    app.include_router(course_router, prefix='/course')
    app.include_router(homework_router, prefix='/homework')
    app.include_router(test_router, prefix='/test')
    app.include_router(ann_router, prefix='/ann')
    app.include_router(ranking_router, prefix='/ranking')
    app.include_router(post_router, prefix='/post')
    app.include_router(copycat_router, prefix='/copycat')
    app.include_router(health_router, prefix='/health')
    app.include_router(user_router, prefix='/user')
    app.include_router(user_options_router, prefix='/user')

    _seed_db()

    logger = logging.getLogger(__name__)
    if settings.SMTP_SERVER is None:
        logger.info(
            "'SMTP_SERVER' is not set. email-related function will be disabled"
        )
    elif settings.SMTP_NOREPLY_PASSWORD is None:
        logger.info("'SMTP_NOREPLY' set but 'SMTP_NOREPLY_PASSWORD' not")

    return app


def _seed_db():
    if not User('first_admin'):
        ADMIN = {
            'username': 'first_admin',
            'password': 'firstpasswordforadmin',
            'email': 'i.am.first.admin@noj.tw',
        }
        PROFILE = {
            'displayed_name': 'the first admin',
            'bio': 'I am super good!!!!!',
        }
        admin = User.signup(**ADMIN)
        admin.update(
            active=True,
            role=0,
            profile=PROFILE,
        )
    if not Course('Public'):
        Course.add_course('Public', 'first_admin')


app = create_app()
