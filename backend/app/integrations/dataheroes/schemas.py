"""Pydantic models for the DataHeroes (Platrum BFF) task-list responses."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class DHTask(BaseModel):
    """One "communication" (call task) from DataHeroes taskList/getData.

    Fields are snake_case; the camelCase JSON keys are mapped via the alias
    generator. Only the fields we use are declared; the rest is ignored.
    """

    model_config = ConfigDict(
        extra="ignore", alias_generator=to_camel, populate_by_name=True
    )

    communication_id: str
    project_id: str | None = None
    client_id: str | None = None
    client_name_with_num: str | None = None
    client_phone: str | None = None
    status: str | None = None
    activation_id: int | None = None
    activation_name: str | None = None
    client_visit_cnt: int | None = None
    contacted_by_user_name: str | None = None
    contacted_at: str | None = None
