from enum import Enum
from typing import NewType, TypeVar, TypeAlias
from functools import lru_cache
from pydantic import (
    BaseModel,
    ValidationError,
    validator,
    model_validator,
)

from fabric.common.schema import OrmBaseModel, AllOptional, AllQueryOptional

BasePydanticClass: NewType = BaseModel
IdentifierType = TypeVar("IdentifierType", bound=type[Enum])


class _Response(OrmBaseModel):
    class Config:
        from_attributes = True


class _Patch(OrmBaseModel, metaclass=AllOptional): ...


class _QueryFilter(OrmBaseModel, metaclass=AllQueryOptional): ...


class _IdentityFilterClass(OrmBaseModel, metaclass=AllQueryOptional):
    @model_validator(mode="before")
    def at_least_one_field_required(cls, kwargs):
        valids = {}
        for k, v in kwargs.items():
            if k in cls.model_fields.keys() and v is not None:
                valids[k] = v
        if len(valids) < 1:
            raise ValueError("At least one field required")
        return valids


ResponseClass: NewType = _Response
PatchClass: NewType = _Patch
QueryFilterClass: NewType = _QueryFilter
IdentityFilterClass: NewType = _IdentityFilterClass

_fabric_type: TypeAlias = (
    type
    | type[ResponseClass]
    | type[PatchClass]
    | type[QueryFilterClass]
    | type[IdentityFilterClass]
)


class PydanticRouteModelsFabric:
    """Pydantic models type generator - the type container for schema"""

    def __init__(
        self,
        base_class: type[BasePydanticClass],
        identifier: type[BasePydanticClass],
        *,
        response_class: type[ResponseClass] = None,
        patch_class: type[PatchClass] = None,
    ):
        self._base_class = base_class
        self._identifier = identifier
        self._response_class = response_class
        self._patch_class = patch_class

    @staticmethod
    def _class_creator(name, *bases: type[BaseModel]) -> _fabric_type:
        """Just create a class with random name cause fastapi map issues"""
        return type(name, bases, {})

    @property
    def base(self) -> type[BasePydanticClass]:
        return self._base_class

    @property
    @lru_cache(None)
    def response(self) -> type[ResponseClass]:
        if self._response_class is not None:
            parents = (self._response_class,)
        else:
            parents = (self.base, ResponseClass)
        return self._class_creator(
            self._base_class.__name__ + "Response", *parents
        )

    @property
    @lru_cache(None)
    def patch(self) -> type[PatchClass]:
        if self._patch_class is not None:
            parents = (self._patch_class,)
        else:
            parents = (self.base, PatchClass)
        return self._class_creator(
            self._base_class.__name__ + "Optional", *parents
        )

    @property
    @lru_cache(None)
    def query_filter(self) -> type[QueryFilterClass]:
        return self._class_creator(
            self._base_class.__name__ + "Filter",
            *(self._base_class, QueryFilterClass),
        )

    @property
    @lru_cache(None)
    def identity_filter(self) -> type[QueryFilterClass]:
        return self._class_creator(
            self._identifier.__name__ + "IdentityFilter",
            *(self._identifier, IdentityFilterClass),
        )


class CsvError(Exception):
    def __init__(self, row: dict, validation_error: ValidationError):
        self.validation_error = validation_error
        self.row = row
        super().__init__(validation_error)


class CsvMode(str, Enum):
    insert = "insert"
    merge = "merge"


class CsvResult(BaseModel):
    total_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0

    @staticmethod
    def _get_length(value: list | int):
        if isinstance(value, int):
            return value
        return len(value)

    @validator("*", pre=True)
    def count(cls, value):
        return cls._get_length(value)
