from typing import Type, Optional, Any, List, Dict

from pydantic import BaseModel, ConfigDict, create_model
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm.properties import ColumnProperty


def generate_pydantic_schema_from_model(
    model: Type[DeclarativeBase],
    *,
    name: Optional[str] = None,
    config: Optional[ConfigDict] = None,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    only_primary_keys: bool = False,
    only_unique: bool = False,
    make_all_optional: bool = False,
) -> Type[BaseModel]:
    config = config or ConfigDict(from_attributes=True)
    mapper = inspect(model)
    fields: Dict[str, Any] = {}

    for attr in mapper.attrs:
        if not isinstance(attr, ColumnProperty) or not attr.columns:
            continue
        column = attr.columns[0]
        name_ = attr.key

        if include and name_ not in include:
            continue
        if exclude and name_ in exclude:
            continue

        if only_primary_keys and not getattr(column, "primary_key", False):
            continue
        if only_unique and not getattr(column, "unique", False):
            continue

        if hasattr(column.type, "impl") and hasattr(
            column.type.impl, "python_type"
        ):
            python_type = column.type.impl.python_type
        elif hasattr(column.type, "python_type"):
            python_type = column.type.python_type
        else:
            raise ValueError(
                f"Cannot determine python_type for column {column}"
            )

        if column.nullable or make_all_optional:
            python_type = Optional[python_type]

        default = None
        if (
            column.default is None
            and not column.nullable
            and not make_all_optional
        ):
            default = ...
        if make_all_optional:
            default = None

        fields[name_] = (python_type, default)

    schema_name = name or f"{model.__name__}Schema"
    return create_model(schema_name, __config__=config, **fields)
