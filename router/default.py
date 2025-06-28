from typing import Type, Optional, List, Literal

from fastapi import APIRouter

from fabric.cruds.base import CRUDBase
from fabric.routes.defaults import (
    GetAllRoute,
    GetOneRoute,
    CreateRoute,
    UpdateRoute,
    PatchRoute,
    DeleteRoute,
)
from fabric.schemas.defaults import (
    RequestSchema,
    ResponseSchema,
    PatchSchema,
    IdentitySchema,
)

AllowedMethod = Literal[
    "get_all",
    "get_one",
    "create",
    "update",
    "patch",
    "delete",
]


def generate_default_router(
    model: Type,
    get_session,
    *,
    crud_class: Type = CRUDBase,
    prefix: Optional[str] = None,
    tags: Optional[List[str]] = None,
    exclude_fields: Optional[List[str]] = None,
    allowed_methods: Optional[List[AllowedMethod]] = None,
) -> APIRouter:
    exclude_fields = exclude_fields or ["id"]
    request_schema = RequestSchema(model, exclude=exclude_fields)
    response_schema = ResponseSchema(model)
    patch_schema = PatchSchema(model, exclude=exclude_fields)
    identity_schema = IdentitySchema(model)
    crud = crud_class(model)

    route_map = {
        "get_all": GetAllRoute(
            crud=crud,
            response_schema=response_schema,
            filter_schema=patch_schema,
        ),
        "get_one": GetOneRoute(
            crud=crud,
            response_schema=response_schema,
            filter_schema=identity_schema,
        ),
        "create": CreateRoute(
            crud=crud,
            request_schema=request_schema,
            response_schema=response_schema,
        ),
        "update": UpdateRoute(
            crud=crud,
            request_schema=request_schema,
            filter_schema=identity_schema,
        ),
        "patch": PatchRoute(
            crud=crud,
            request_schema=patch_schema,
            filter_schema=identity_schema,
        ),
        "delete": DeleteRoute(
            crud=crud,
            filter_schema=identity_schema,
        ),
    }

    all_methods = list(route_map.keys())
    methods = allowed_methods if allowed_methods is not None else all_methods
    routes = [route_map[m] for m in methods if m in route_map]

    router = APIRouter(
        prefix=prefix or f"/{model.__name__.lower()}",
        tags=tags or [model.__name__.lower()],
    )
    for route in routes:
        route.register(router, get_session)
    return router
