from functools import wraps

from fastapi import HTTPException
from sqlalchemy.exc import StatementError, InvalidRequestError

from exc import DataBaseException


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
