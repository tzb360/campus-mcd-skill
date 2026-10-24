from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Request(Model):
    location: str = Field(min_length=1, max_length=160)
    start: datetime
    deadline: datetime
    budget_cents: int = Field(ge=0, le=100000, strict=True)
    available_minutes: int | None = Field(default=None, gt=0, le=1440, strict=True)
    max_walk_minutes: int = Field(default=15, ge=0, le=120, strict=True)
    eat_minutes: int = Field(default=15, ge=1, le=120, strict=True)
    buffer_minutes: int = Field(default=5, ge=0, le=120, strict=True)
    max_kcal: int | None = Field(default=None, gt=0, le=10000, strict=True)
    prefer: list[str] = Field(default_factory=list, max_length=10)
    avoid: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("start", "deadline")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("时间必须含时区，例如 2026-10-24T12:00:00+08:00")
        return value

    @model_validator(mode="after")
    def ordered(self):
        if not 0 < (self.deadline - self.start).total_seconds() <= 86400:
            raise ValueError("返课时间须晚于出发时间，窗口不超过24小时")
        return self


class Store(Model):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    walk_minutes: int | None = Field(default=None, ge=0, le=240, strict=True)
    walk_basis: str = Field(default="未提供可靠步行耗时", max_length=240)
    wait_minutes: int | None = Field(default=None, ge=0, le=180, strict=True)
    wait_basis: str = Field(default="未提供排队及出餐耗时", max_length=240)


class Offer(Model):
    id: str = Field(min_length=1, max_length=120)
    store_id: str
    name: str = Field(min_length=1, max_length=240)
    payable_cents: int = Field(ge=0, le=100000, strict=True)
    baseline_cents: int | None = Field(default=None, ge=0, le=100000, strict=True)
    kcal: float | None = Field(default=None, ge=0, le=10000, strict=True)
    tags: list[str] = Field(default_factory=list, max_length=20)
    coupon: str | None = Field(default=None, max_length=160)
    available: bool = True
    quote_at: datetime
    expires_at: datetime | None = None
    evidence: str = Field(min_length=1, max_length=240)

    @field_validator("quote_at", "expires_at")
    @classmethod
    def aware(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("报价及有效期必须含时区")
        return value


class Snapshot(Model):
    mode: Literal["mock", "live"]
    stores: list[Store] = Field(max_length=3)
    offers: list[Offer] = Field(max_length=12)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def references(self):
        ids = [s.id for s in self.stores]
        if len(set(ids)) != len(ids):
            raise ValueError("门店ID重复")
        if len({o.id for o in self.offers}) != len(self.offers):
            raise ValueError("方案ID重复")
        if any(o.store_id not in ids for o in self.offers):
            raise ValueError("方案引用了未知门店")
        return self
