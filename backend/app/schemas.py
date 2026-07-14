from datetime import date, datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


class UserAuth(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_not_empty(cls, v):
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("Email must not be empty")
        return v.strip()

    @field_validator("password", mode="before")
    @classmethod
    def validate_password_not_empty(cls, v):
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("Password must not be empty")
        return v


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str


class Token(BaseModel):
    access_token: str
    token_type: str


class CycleCreate(BaseModel):
    start_date: date
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "CycleCreate":
        if self.end_date is not None and self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class CycleUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "CycleUpdate":
        if self.start_date is not None and self.end_date is not None:
            if self.end_date <= self.start_date:
                raise ValueError("end_date must be after start_date")
        return self


class CycleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    start_date: date
    end_date: date | None
    cycle_length: int | None
    created_at: datetime
    updated_at: datetime


class PredictionRange(BaseModel):
    earliest: date | None
    latest: date | None


class PredictionResponse(BaseModel):
    predicted_next_period_start: date | None
    average_cycle_length: float
    current_cycle_day: int | None
    confidence: Literal["low", "medium", "high"]
    basis: Literal["default", "limited_data", "personal_average"]
    predicted_range: PredictionRange | None = None
    predicted_ovulation_date: date | None = None
    fertile_window_start: date | None = None
    fertile_window_end: date | None = None
