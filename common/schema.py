from pydantic import BaseModel
from pydantic._internal._model_construction import ModelMetaclass


class OrmBaseModel(BaseModel):
    """Just only base model with Config.from_attributes = True

    this means that a boxed method <from_orm> is implemented,
    as well as ORM objects are automatically converted if a scheme
    with such a parent is specified in route response_model
    """

    class Config:
        from_attributes = True


class AllOptional(ModelMetaclass):
    """Add as metaclass for (metaclass=AllOptional)
    what functionality:
    all fields are optional (may not be present in the input json),
    the default values of all fields are null,
    an empty object is a valid object

    can be used for <patch> methods that change only the data
    for the object that is passed to the body
    """

    def __new__(mcls, name, bases, namespaces, **kwargs):
        annotations = namespaces.get("__annotations__", {})
        for base in bases:
            annotations.update(base.__annotations__)
            for super_ in base.mro():
                # add supers from mro
                if issubclass(super_, BaseModel) and super_ != BaseModel:
                    annotations.update(super_.__annotations__)
        for field in annotations:
            if not field.startswith("__"):
                annotations[field] = annotations[field] | None
                namespaces[field] = None
        namespaces["__annotations__"] = annotations
        return super().__new__(mcls, name, bases, namespaces, **kwargs)
