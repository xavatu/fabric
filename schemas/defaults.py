from .generate import generate_pydantic_schema_from_model

RequestSchema = lambda model, **kwargs: generate_pydantic_schema_from_model(
    model,
    exclude=kwargs.pop("exclude", ["id"]),
    name=kwargs.pop("name", f"{model.__name__}Request"),
    **kwargs,
)
ResponseSchema = lambda model, **kwargs: generate_pydantic_schema_from_model(
    model, name=kwargs.pop("name", f"{model.__name__}Response"), **kwargs
)
PatchSchema = lambda model, **kwargs: generate_pydantic_schema_from_model(
    model,
    exclude=kwargs.pop("exclude", ["id"]),
    name=kwargs.pop("name", f"{model.__name__}Patch"),
    make_all_optional=True,
    **kwargs,
)
IdentitySchema = lambda model, **kwargs: generate_pydantic_schema_from_model(
    model,
    only_primary_keys=True,
    name=kwargs.pop("name", f"{model.__name__}Identity"),
    **kwargs,
)
