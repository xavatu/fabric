from typing import Container, Optional, Type

from pydantic import ConfigDict, BaseModel, create_model
from sqlalchemy.inspection import inspect
from sqlalchemy.orm.properties import ColumnProperty


FromAttributesConfig = lambda: ConfigDict(from_attributes=True)


def get_model_identity_schema(
    model: Type,
    *,
    config: ConfigDict = None,
    include_unique: bool = False,
) -> Type[BaseModel]:
    if config is None:
        config = FromAttributesConfig()
    mapper = inspect(model)
    fields = {}

    for attr in mapper.attrs:
        if not isinstance(attr, ColumnProperty) or not attr.columns:
            continue
        name = attr.key
        column = attr.columns[0]
        python_type: Optional[type] = None
        if not getattr(column, "primary_key") and (
            include_unique and not getattr(column, "unique")
        ):
            continue
        if hasattr(column.type, "impl"):
            if hasattr(column.type.impl, "python_type"):
                python_type = column.type.impl.python_type
        elif hasattr(column.type, "python_type"):
            python_type = column.type.python_type
        assert python_type, f"Could not infer python_type for {column}"
        default = None
        if column.default is None and not column.nullable:
            default = ...
        if not column.primary_key:
            python_type = Optional[python_type]
            default = None
        fields[name] = (python_type, default)

    pydantic_model = create_model(model.__name__, __config__=config, **fields)
    return pydantic_model


def get_model_schema(
    model: Type,
    *,
    config: ConfigDict = None,
    exclude: list[str] = None,
) -> Type[BaseModel]:
    if config is None:
        config = FromAttributesConfig()
    mapper = inspect(model)
    fields = {}
    exclude = exclude if exclude else []
    for attr in mapper.attrs:
        if not isinstance(attr, ColumnProperty) or not attr.columns:
            continue
        name = attr.key
        if name in exclude:
            continue
        column = attr.columns[0]
        python_type: Optional[type] = None
        if hasattr(column.type, "impl"):
            if hasattr(column.type.impl, "python_type"):
                python_type = column.type.impl.python_type
        elif hasattr(column.type, "python_type"):
            python_type = column.type.python_type
        assert python_type, f"Could not infer python_type for {column}"
        default = None
        if column.default is None and not column.nullable:
            default = ...
        if column.nullable:
            python_type = Optional[python_type]
        fields[name] = (python_type, default)

    pydantic_model = create_model(model.__name__, __config__=config, **fields)
    return pydantic_model
