import logging
from fastapi import APIRouter, Depends, Request

from .auth import login_required, identity_verify
from .utils import *

__all__ = ['test_router']

logger = logging.getLogger(__name__)

test_router = APIRouter()


@test_router.get('')
def test(user=Depends(login_required)):
    return HTTPResponse(user.username)


@test_router.get('/role')
def role(user=identity_verify(0, 1, ...)):
    return HTTPResponse(str(user.obj.role))


@test_router.get('/log')
def log():
    logger.debug('this is a DEBUG log')
    logger.info('this is a INFO log')
    logger.warning('this is a WARNING log')
    logger.error('this is a ERROR log')
    logger.critical('this is a CRITICAL log')
    return HTTPResponse('check the log')


@test_router.get('/header')
def check_header(request: Request):
    logger.debug(f'{request.headers}')
    return HTTPResponse('ok')
