import csv
from enum import Enum
from io import StringIO
from typing import Callable, Awaitable

from fastapi import (
    APIRouter,
    Depends,
    Response,
    UploadFile,
    File,
    HTTPException,
)
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from fabric.reference_routes.route_schema import (
    PydanticRouteModelsFabric,
    CsvMode,
    CsvError,
)
from fabric.common.crud import (
    resolve_crud,
    CRUDBaseCommonMethodType,
    CrudType,
    CRUDBase,
)
from fabric.exc import (
    NoResultFoundException,
    IntegrityErrorException,
    db_exception_wrapper,
    make_dependable,
)


class Method(str, Enum):
    get_all = "get_all"
    get_one = "get_one"
    post = "post"
    csv = "csv"
    put = "put"
    patch = "patch"
    delete = "delete"


def generate_routes_pack(
    router_prefix: str,
    common_name: str,
    crud: CrudType,
    fabric: PydanticRouteModelsFabric,
    get_session,
    *,
    tags: list[str] = None,
    include_in_schema=True,
    default_offset_limit: tuple[int, int] = (0, 100),
    custom_route_awaitable: dict[Method, CRUDBaseCommonMethodType] = None,
    allowed_methods: list[Method] = None,
    excluded_methods: list[Method] = None,
    csv_preparer: Callable[
        [AsyncSession, dict[str, ...], CRUDBase], Awaitable[dict[str, ...]]
    ] = None,
) -> APIRouter:
    tags = tags or [router_prefix.strip("/").replace("-", " ")]
    crud, get_crud = resolve_crud(crud)
    custom_route_awaitable = custom_route_awaitable or {}
    allowed_methods = allowed_methods or list(Method)
    excluded_methods = excluded_methods or []
    allowed_methods = set(allowed_methods).difference(excluded_methods)

    router = APIRouter(
        prefix=router_prefix, tags=tags, include_in_schema=include_in_schema
    )

    def not_found(method):
        if method not in allowed_methods:
            raise HTTPException(status_code=400, detail="Not found")

    @router.get(
        "",
        response_model=list[fabric.response],
        name=f"Get all {common_name} objects",
        include_in_schema=Method.get_all in allowed_methods,
    )
    async def get_all_commons(
        filter_model: fabric.query_filter = Depends(fabric.query_filter),
        offset: int = default_offset_limit[0],
        limit: int = default_offset_limit[-1],
        method_crud: crud = Depends(get_crud),
        session: AsyncSession = Depends(get_session),
    ):
        not_found(Method.get_all)
        custom_method = custom_route_awaitable.get(Method.get_all)
        filter_dict = filter_model.model_dump(exclude_none=True)

        if custom_method:
            return await custom_method(session, offset, limit)

        return await method_crud.get_multi(
            session, filter_dict=filter_dict, offset=offset, limit=limit
        )

    @router.get(
        "/",
        response_model=fabric.response,
        name=f"Get single {common_name} object",
        include_in_schema=Method.get_one in allowed_methods,
    )
    @db_exception_wrapper(NoResultFoundException)
    async def get_one_common(
        identity_filter: fabric.identity_filter = Depends(
            make_dependable(fabric.identity_filter)
        ),
        method_crud: crud = Depends(get_crud),
        session: AsyncSession = Depends(get_session),
    ):
        not_found(Method.get_one)
        custom_method = custom_route_awaitable.get(Method.get_one)
        filter_dict = identity_filter.model_dump(exclude_none=True)

        if custom_method:
            return await custom_method(session, filter_dict)
        result = await method_crud.get_one(session, filter_dict=filter_dict)

        await session.commit()
        return result

    @router.post(
        "/",
        response_model=fabric.response,
        name=f"Create {common_name} object",
        include_in_schema=Method.post in allowed_methods,
    )
    @db_exception_wrapper(IntegrityErrorException)
    async def create_common(
        payload: fabric.base,
        method_crud: crud = Depends(get_crud),
        session: AsyncSession = Depends(get_session),
    ):
        not_found(Method.post)
        custom_method = custom_route_awaitable.get(Method.post)
        if custom_method:
            return await custom_method(session, payload)

        result = fabric.response.model_validate(
            await method_crud.create(session, obj_in=payload)
        )
        await session.commit()
        return result

    def parse_csv(file: bytes) -> list[fabric.base]:
        foo = StringIO(file.decode("utf-8"))
        result = []
        for row in csv.DictReader(foo):
            try:
                result.append(fabric.base(**row))
            except ValidationError as e:
                raise CsvError(row, e)
        return result

    @router.post(
        "/csv",
        response_class=Response,
        name=f"Create {common_name} from csv",
        include_in_schema=Method.csv in allowed_methods,
    )
    @db_exception_wrapper(IntegrityErrorException)
    async def create_common_from_csv(
        mode: CsvMode = CsvMode.merge,
        method_crud: CRUDBase = Depends(get_crud),
        session: AsyncSession = Depends(get_session),
        file: UploadFile = File(..., media_type="text/csv"),
    ):
        not_found(Method.csv)
        try:
            data = await file.read()
            csv_dict = await run_in_threadpool(parse_csv, data)
        except CsvError as e:
            raise HTTPException(
                status_code=400,
                detail={"row": e.row, "detail": e.validation_error.errors()},
            )
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=e.errors())
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            await file.close()

        if csv_preparer is not None:
            csv_dict = await csv_preparer(session, csv_dict, method_crud)

        await method_crud.bulk_merge_create(
            session, obj_list=csv_dict, is_simple_insert=mode is CsvMode.insert
        )
        await session.commit()
        return None

    @router.patch(
        "/{identifier}",
        response_class=Response,
        name=f"Change fields of {common_name} object",
        include_in_schema=Method.patch in allowed_methods,
    )
    @db_exception_wrapper(NoResultFoundException, IntegrityErrorException)
    async def update_common_fields(
        payload: fabric.patch,
        identity_filter: fabric.identity_filter = Depends(
            make_dependable(fabric.identity_filter)
        ),
        method_crud: crud = Depends(get_crud),
        session: AsyncSession = Depends(get_session),
    ):
        not_found(Method.patch)
        custom_method = custom_route_awaitable.get(Method.patch)
        filter_dict = identity_filter.model_dump(exclude_none=True)

        if custom_method:
            return await custom_method(session, filter_dict, payload, True)

        changes = payload.dict(exclude_none=True)
        if not changes:
            raise IntegrityErrorException(
                "There are no info in the input data"
            )
        await method_crud.update(
            session,
            filter_dict=filter_dict,
            update_dict=changes,
            is_patch=True,
        )
        await session.commit()

    @router.put(
        "/{identifier}",
        response_class=Response,
        name=f"Change {common_name} object",
        include_in_schema=Method.put in allowed_methods,
    )
    @db_exception_wrapper(NoResultFoundException, IntegrityErrorException)
    async def change_common(
        payload: fabric.base,
        identity_filter: fabric.identity_filter = Depends(
            make_dependable(fabric.identity_filter)
        ),
        method_crud: crud = Depends(get_crud),
        session: AsyncSession = Depends(get_session),
    ):
        not_found(Method.put)
        custom_method = custom_route_awaitable.get(Method.put)
        filter_dict = identity_filter.model_dump(exclude_none=True)

        if custom_method:
            return await custom_method(session, filter_dict, payload, False)

        changes = payload.dict()
        await method_crud.update(
            session,
            filter_dict=filter_dict,
            update_dict=changes,
            is_patch=False,
        )
        await session.commit()

    @router.delete(
        "/{identifier}",
        name=f"Delete {common_name} object",
        include_in_schema=Method.delete in allowed_methods,
    )
    @db_exception_wrapper(NoResultFoundException, IntegrityErrorException)
    async def delete_common(
        identity_filter: fabric.identity_filter = Depends(
            make_dependable(fabric.identity_filter)
        ),
        method_crud: crud = Depends(get_crud),
        session: AsyncSession = Depends(get_session),
    ):
        not_found(Method.delete)
        custom_method = custom_route_awaitable.get(Method.delete)
        filter_dict = identity_filter.model_dump(exclude_none=True)

        if custom_method:
            return await custom_method(session, filter_dict)

        await method_crud.delete(session, filter_dict=filter_dict)
        await session.commit()

    return router
