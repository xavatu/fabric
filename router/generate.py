from typing import Callable, AsyncGenerator

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from fabric.routes.base import RouteBase


def generate_router(
    *routes: RouteBase,
    get_session: Callable[[], AsyncGenerator[AsyncSession, None]],
    **router_kwargs
) -> APIRouter:
    router = APIRouter(**router_kwargs)

    for route in routes:
        route.register(router, get_session)

    return router
