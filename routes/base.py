from enum import StrEnum
from typing import Type, Callable, AsyncGenerator

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from fabric.cruds.base import CRUDBase


class Method(StrEnum):
    get_all = "get_all"
    get_one = "get_one"
    create = "create"
    update = "update"
    patch = "patch"
    delete = "delete"


class RouteBase:
    method: Method

    def __init__(
        self,
        crud: CRUDBase,
        request_schema: Type[BaseModel] = None,
        response_schema: Type[BaseModel] = None,
        filter_schema: Type[BaseModel] = None,
    ):
        self.crud = crud
        self.request_schema = request_schema
        self.response_schema = response_schema
        self.filter_schema = filter_schema

    def register(
        self,
        router: APIRouter,
        get_session: Callable[[], AsyncGenerator[AsyncSession, None]],
    ):
        raise NotImplementedError
