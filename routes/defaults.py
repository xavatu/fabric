from typing import List

from fastapi import Depends, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from fabric.exc import (
    NoResultFoundException,
    IntegrityErrorException,
    db_exception_wrapper,
)
from .base import RouteBase, Method


class GetAllRoute(RouteBase):
    method = Method.get_all

    def register(self, router: APIRouter, get_session):
        crud = self.crud
        filter_schema = self.filter_schema
        response_schema = self.response_schema

        @router.get(
            "",
            response_model=List[response_schema],
        )
        async def get_all(
            offset: int = 0,
            limit: int = 100,
            filter_model: filter_schema = Depends(filter_schema),
            session: AsyncSession = Depends(get_session),
        ):
            filter_dict = filter_model.model_dump(exclude_none=True)
            return await crud.get_multi(
                session, filter_dict=filter_dict, offset=offset, limit=limit
            )


class GetOneRoute(RouteBase):
    method = Method.get_one

    def register(self, router: APIRouter, get_session):
        crud = self.crud
        filter_schema = self.filter_schema
        response_schema = self.response_schema

        @router.get(
            "/",
            response_model=response_schema,
        )
        @db_exception_wrapper(NoResultFoundException)
        async def get_one(
            identity_filter: filter_schema = Depends(filter_schema),
            session: AsyncSession = Depends(get_session),
        ):
            filter_dict = identity_filter.model_dump(exclude_none=True)
            result = await crud.get_one(session, filter_dict=filter_dict)
            await session.commit()
            return result


class CreateRoute(RouteBase):
    method = Method.create

    def register(self, router: APIRouter, get_session):
        crud = self.crud
        request_schema = self.request_schema
        response_schema = self.response_schema

        @router.post("/", response_model=response_schema)
        async def create(
            payload: request_schema,
            session: AsyncSession = Depends(get_session),
        ):
            obj = await crud.create(session, obj_in=payload.model_dump())
            await session.commit()
            return response_schema.model_validate(obj)


class UpdateRoute(RouteBase):
    method = Method.update

    def register(self, router: APIRouter, get_session):
        crud = self.crud
        request_schema = self.request_schema
        filter_schema = self.filter_schema

        @router.put("/")
        @db_exception_wrapper(NoResultFoundException, IntegrityErrorException)
        async def update(
            payload: request_schema,
            identity_filter: filter_schema = Depends(filter_schema),
            session: AsyncSession = Depends(get_session),
        ):
            filter_dict = identity_filter.model_dump(exclude_none=True)
            changes = payload.model_dump()
            affected = await crud.update(
                session,
                filter_dict=filter_dict,
                update_dict=changes,
                is_patch=False,
            )
            await session.commit()
            return affected


class PatchRoute(RouteBase):
    method = Method.patch

    def register(self, router: APIRouter, get_session):
        crud = self.crud
        request_schema = self.request_schema
        filter_schema = self.filter_schema

        @router.patch("/")
        @db_exception_wrapper(NoResultFoundException, IntegrityErrorException)
        async def patch(
            payload: request_schema,
            identity_filter: filter_schema = Depends(filter_schema),
            session: AsyncSession = Depends(get_session),
        ):
            filter_dict = identity_filter.model_dump(exclude_none=True)
            changes = payload.model_dump(exclude_none=True)
            if not changes:
                raise IntegrityErrorException(
                    "There are no info in the input data"
                )
            affected = await crud.update(
                session,
                filter_dict=filter_dict,
                update_dict=changes,
                is_patch=True,
            )
            await session.commit()
            return affected


class DeleteRoute(RouteBase):
    method = Method.delete

    def register(self, router: APIRouter, get_session):
        crud = self.crud
        filter_schema = self.filter_schema

        @router.delete("/")
        @db_exception_wrapper(NoResultFoundException, IntegrityErrorException)
        async def delete(
            identity_filter: filter_schema = Depends(filter_schema),
            session: AsyncSession = Depends(get_session),
        ):
            filter_dict = identity_filter.model_dump(exclude_none=True)
            affected = await crud.delete(session, filter_dict=filter_dict)
            await session.commit()
            return affected
