from enum import Enum
from typing import NewType, TypeVar, TypeAlias
from functools import lru_cache
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError, validator

from fabric.common.schema import OrmBaseModel, AllOptional, AllQueryOptional

BasePydanticClass: NewType = BaseModel
IdentifierType = TypeVar("IdentifierType", bound=type[Enum])


class _Response(OrmBaseModel):
    id: int

    class Config:
        from_attributes = True


class _Patch(OrmBaseModel, metaclass=AllOptional): ...


class _Convertor(OrmBaseModel, metaclass=AllOptional):
    @classmethod
    def _base_get_identity_dict(
        cls, identifier_type: IdentifierType, identifier: str
    ):
        try:
            return cls(**{identifier_type.value: identifier}).dict(
                exclude_none=True
            )
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=e.errors())

    @classmethod
    def get_identity_dict(
        cls, identifier_type: IdentifierType, identifier: str
    ):
        raise NotImplementedError()


class _QueryFilter(OrmBaseModel, metaclass=AllQueryOptional): ...


ResponseClass: NewType = _Response
PatchClass: NewType = _Patch
ConvertorClass: NewType = _Convertor
QueryFilterClass: NewType = _QueryFilter

_fabric_type: TypeAlias = (
    type
    | type[ResponseClass]
    | type[ConvertorClass]
    | type[PatchClass]
    | type[QueryFilterClass]
)


class PydanticRouteModelsFabric:
    """Pydantic models type generator - the type container for schema"""

    def __init__(
        self,
        base_class: type[BasePydanticClass],
        identifier: IdentifierType,
        *,
        identifier_id: str = "id",
        response_class: type[ResponseClass] = None,
        patch_class: type[PatchClass] = None,
        convertor_class: type[ConvertorClass] = None,
    ):
        self._base_class = base_class
        self._identifier = identifier
        self._identifier_id = identifier_id
        self._response_class = response_class
        self._patch_class = patch_class
        self._convertor_class = convertor_class

    @staticmethod
    def _class_creator(name, *bases: type[BaseModel]) -> _fabric_type:
        """Just create a class with random name cause fastapi map issues"""
        return type(name, bases, {})

    @property
    def identifier(self):
        return self._identifier

    @property
    def identifier_id(self):
        return getattr(self.identifier, self._identifier_id)

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
    def convertor(self) -> type[ConvertorClass]:
        identifier_enum = self.identifier

        class _ConvertorClass(
            self._base_class, self._convertor_class or ConvertorClass
        ):
            @classmethod
            def get_identity_dict(
                cls, identifier_type: identifier_enum, identifier: str
            ):
                return cls._base_get_identity_dict(identifier_type, identifier)

        return self._class_creator(
            self._base_class.__name__ + "Convertor",
            _ConvertorClass,
            self.response,
        )

    @property
    @lru_cache(None)
    def query_filter(self) -> type[QueryFilterClass]:
        return self._class_creator(
            self._base_class.__name__ + "Filter",
            *(self._base_class, QueryFilterClass),
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
