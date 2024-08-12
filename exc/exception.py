from abc import ABC
from typing import TypeAlias

from sqlalchemy.exc import (
    StatementError,
    InvalidRequestError,
    NoResultFound,
    IntegrityError,
)

ExceptionType: TypeAlias = (
    tuple[type[StatementError | InvalidRequestError]]
    | type[StatementError | InvalidRequestError]
)


class DataBaseException(ABC, Exception):
    def __init__(
        self,
        detail: str = None,
        code: int = None,
        exception: ExceptionType = None,
    ):
        self._exception = exception
        self._detail = detail
        self._code = code

    @property
    def exception(self) -> ExceptionType:
        return self._exception or self.default_exception()

    @classmethod
    def default_exception(cls) -> ExceptionType:
        raise NotImplementedError()

    @property
    def detail(self) -> str | dict:
        return self._detail or self.default_detail()

    @classmethod
    def default_detail(cls) -> str | dict:
        raise NotImplementedError()

    @property
    def code(self) -> int:
        return self._code or self.default_code()

    @classmethod
    def default_code(cls) -> int:
        raise NotImplementedError()

    @staticmethod
    def get_string_value(exc: StatementError):
        try:
            return "; ".join(
                pg_error.split(":", 1)[-1].strip()
                for pg_error in exc.orig.args
            )
        except Exception as e:
            return str(e)


class NoResultFoundException(DataBaseException):
    @classmethod
    def default_detail(cls) -> str | dict:
        return "The item not found"

    @classmethod
    def default_exception(cls) -> ExceptionType:
        return NoResultFound

    @classmethod
    def default_code(cls) -> int:
        return 404


class IntegrityErrorException(DataBaseException):
    @classmethod
    def default_exception(cls) -> ExceptionType:
        return IntegrityError

    @classmethod
    def default_detail(cls) -> str | dict:
        return "Got an error on add: {}"

    @classmethod
    def default_code(cls) -> int:
        return 400
