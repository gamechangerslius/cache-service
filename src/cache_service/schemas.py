"""Request and response models: the public API contract.

Kept free of FastAPI imports so the CLI can validate its input with the same rules.
"""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

# Bound the work a single request can cause (transformer calls, DB rows, bind parameters).
# They are part of the API contract, hence constants rather than deployment settings.
MAX_ITEMS = 1_000
MAX_STRING_LENGTH = 1_000

# Constraining the string also makes pydantic reject unpaired surrogates ("\ud800" escapes
# in JSON), which the database could not encode and would turn into a 500.
Item = Annotated[str, StringConstraints(max_length=MAX_STRING_LENGTH)]


class PayloadCreate(BaseModel):
    model_config = ConfigDict(
        # A misspelled key must fail loudly instead of being silently dropped.
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "list_1": ["first string", "second string", "third string"],
                    "list_2": ["other string", "another string", "last string"],
                }
            ]
        },
    )

    list_1: list[Item] = Field(min_length=1, max_length=MAX_ITEMS)
    list_2: list[Item] = Field(min_length=1, max_length=MAX_ITEMS)

    @model_validator(mode="after")
    def _lists_have_same_length(self) -> Self:
        if len(self.list_1) != len(self.list_2):
            raise ValueError(
                "list_1 and list_2 must have the same length "
                f"(got {len(self.list_1)} and {len(self.list_2)})"
            )
        return self


class PayloadCreated(BaseModel):
    id: UUID
    message: str = Field(examples=["Payload created", "Payload already exists"])


class PayloadRead(BaseModel):
    output: str = Field(
        examples=[
            "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"
        ]
    )


class HealthResponse(BaseModel):
    status: Literal["ok"]
