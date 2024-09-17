import json
from functools import wraps
from inspect import signature

from fastapi import HTTPException
from pydantic_core import ValidationError
from sqlalchemy.exc import StatementError, InvalidRequestError

from fabric.exc import DataBaseException


def db_exception_wrapper(*exception: type[DataBaseException]) -> ():
    def outer_wrapper(func) -> ():
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except DataBaseException as e:
                raise HTTPException(status_code=e.code, detail=e.detail)
            except (StatementError, InvalidRequestError) as e:
                for ex in exception:
                    if not isinstance(e, ex.default_exception()):
                        continue
                    raise HTTPException(
                        status_code=ex.default_code(),
                        detail=ex.default_detail().format(
                            ex.get_string_value(e)
                        ),
                    )
                raise

        return wrapper

    return outer_wrapper


def make_dependable(cls):
    """
    Pydantic BaseModels are very powerful because we get lots of validations and type checking right out of the box.
    FastAPI can accept a BaseModel as a route Dependency and it will automatically handle things like documentation
    and error handling. However, if we define custom validators then the errors they raise are not handled, leading
    to HTTP 500's being returned.

    To better understand this issue, you can visit https://github.com/tiangolo/fastapi/issues/1474 for context.

    A workaround proposed there adds a classmethod which attempts to init the BaseModel and handles formatting of
    any raised ValidationErrors, custom or otherwise. However, this means essentially duplicating the class's
    signature. This function automates the creation of a workaround method with a matching signature so that you
    can avoid code duplication.

    usage:
    async def fetch(thing_request: ThingRequest = Depends(make_dependable(ThingRequest))):
    """

    def init_cls_and_handle_errors(*args, **kwargs):
        try:
            signature(init_cls_and_handle_errors).bind(*args, **kwargs)
            return cls(*args, **kwargs)
        except ValidationError as e:
            raise HTTPException(422, detail=json.loads(e.json()))

    init_cls_and_handle_errors.__signature__ = signature(cls)
    return init_cls_and_handle_errors
