from typing import (
    TypeVar,
    Generator,
    Any,
    Generic,
    TypeAlias,
    Callable,
    Awaitable,
)

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select, delete, update, UniqueConstraint, or_, and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine.cursor import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import Select

from fabric.exc import NoResultFoundException


Base = declarative_base()
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)


CRUDBaseCommonMethodType: TypeAlias = (
    Callable[
        [AsyncSession, dict[str, ...], int, int], Awaitable[list[ModelType]]
    ]
    | Callable[[AsyncSession, dict[str, ...]], Awaitable[ModelType] | None]
    | Callable[[AsyncSession, dict[str, ...], dict[str, ...], bool], None]
)


class CRUDBase(Generic[ModelType, CreateSchemaType]):
    def __init__(self, model: type[ModelType]):
        """
        CRUD object with default methods to
            Create, Read, Update, Delete (CRUD).
        **Parameters**
        * `model`: A SQLAlchemy model class
        * `schema`: A Pydantic model (schema) class
        """
        self._model = model

    def _generate_where_cause(
        self, filter_dict: dict[str, ...] | None = None
    ) -> Generator[bool, Any, None]:
        filter_dict = filter_dict or {}
        return (
            getattr(self._model, field) == value
            for field, value in filter_dict.items()
        )

    @property
    def _select_model(self) -> Select:
        """can be used for config options with inload"""
        return select(self._model)

    async def get_multi(
        self,
        session: AsyncSession,
        filter_dict: dict[str, ...] | None = None,
        offset: int = 0,
        limit: int | None = 100,
    ) -> list[ModelType]:
        stmt = self._select_model.where(
            *self._generate_where_cause(filter_dict)
        ).offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        return list((await session.execute(stmt)).scalars().all())

    async def get_one(
        self, session: AsyncSession, filter_dict: dict[str, ...]
    ) -> ModelType:
        stmt = self._select_model.where(
            *self._generate_where_cause(filter_dict)
        )
        return (await session.execute(stmt)).scalars().one()

    async def create(
        self, session: AsyncSession, *, obj_in: dict | CreateSchemaType
    ) -> ModelType:
        obj_in_data = obj_in
        if isinstance(obj_in_data, BaseModel):
            obj_in_data = obj_in.model_dump()
        db_obj = self._model(**obj_in_data)  # type: ignore
        session.add(db_obj)
        await session.flush([db_obj])
        return db_obj

    async def bulk_merge_create(
        self,
        session: AsyncSession,
        *,
        obj_list: list[dict | CreateSchemaType],
        is_simple_insert=False,
    ) -> None:
        final_in_data = [
            jsonable_encoder(obj) if not isinstance(obj, dict) else obj
            for obj in obj_list
        ]
        stmt = insert(self._model).values(final_in_data)
        if is_simple_insert:
            await session.execute(stmt)
            return None

        unique_constr_names = [
            v.name
            for c in self._model.__table__.constraints
            for v in c.columns.values()
            if isinstance(c, UniqueConstraint)
        ]

        if not unique_constr_names:
            await session.execute(stmt)
            return None

        if len(unique_constr_names) == 1:
            # if only one unique

            column_to_update = (
                {c.name for c in self._model.__table__.columns}
                - set(unique_constr_names)
                - {"id"}
            )

            if not column_to_update:
                # if it has no more fields to update
                await session.execute(stmt)
                return None

            stmt = stmt.on_conflict_do_update(
                index_elements=unique_constr_names,
                set_={
                    column: getattr(stmt.excluded, column)
                    for column in column_to_update
                },
            )
            await session.execute(stmt)
            return None

        data_tuple_dict: dict[tuple, dict] = {
            tuple(dict_.get(f) for f in unique_constr_names): dict_
            for dict_ in final_in_data
        }

        exist_stmt = select(self._model).where(
            or_(
                and_(
                    *(
                        getattr(self._model, a) == b
                        for a, b in dict(zip(unique_constr_names, dt)).items()
                    )
                )
                for dt in data_tuple_dict
            )
        )

        existing_rows = (await session.execute(exist_stmt)).scalars().all()
        to_update = []
        for model in existing_rows:
            row_key = tuple(getattr(model, v) for v in unique_constr_names)
            try:
                for k, v in data_tuple_dict.pop(row_key).items():
                    setattr(model, k, v)
                to_update.append(model)
            except KeyError:
                continue
        to_insert = [self._model(**v) for v in data_tuple_dict.values()]

        session.add_all(to_insert)
        await session.flush(to_update + to_insert)
        return None

    async def update(
        self,
        session: AsyncSession,
        *,
        filter_dict: dict[str, ...],
        update_dict: dict[str, ...],
        is_patch=True,
        raise_on_not_affected=True,
    ) -> None:
        """If is_patch = True - update only not nullable fields
        in other case set possible null values"""

        if is_patch:
            update_dict = {
                k: v for k, v in update_dict.items() if v is not None
            }
        update_stmt = (
            update(self._model)
            .where(*self._generate_where_cause(filter_dict))
            .values(**update_dict)
        )
        result: CursorResult = await session.execute(update_stmt)
        if raise_on_not_affected and not result.rowcount:
            raise NoResultFoundException()
        return None

    async def delete(
        self,
        session: AsyncSession,
        filter_dict: dict[str, ...],
        raise_on_not_affected=True,
    ) -> None:
        delete_stmt = delete(self._model).where(
            *self._generate_where_cause(filter_dict)
        )
        result: CursorResult = await session.execute(delete_stmt)
        await session.flush()
        if raise_on_not_affected and not result.rowcount:
            raise NoResultFoundException()
        return None


CrudType: TypeAlias = CRUDBase | Callable[[], CRUDBase]  # ()->CRUDBase


def resolve_crud(crud: CrudType) -> tuple[CRUDBase, Callable[[], CRUDBase]]:
    if isinstance(crud, CRUDBase):
        return crud, lambda: crud
    return crud(), crud
