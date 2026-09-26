from pydantic import BaseModel, ConfigDict


class BaseSchemaModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        populate_by_name=True,
    )


class ServiceInfo(BaseSchemaModel):
    healthy: bool = True