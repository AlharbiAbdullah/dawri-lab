"""Validate the three component shapes sent to the browser."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from dawri.api_models import Standing, TeamMetrics


class Column(BaseModel, extra="forbid", strict=True):
    key: str
    label: str
    format: Literal["text", "integer", "decimal"]


class PageProps(BaseModel, extra="forbid", strict=True):
    title: str


class TextProps(BaseModel, extra="forbid", strict=True):
    content: str


class StandingsProps(BaseModel, extra="forbid", strict=True):
    title: Literal["Standings"]
    columns: list[Column]
    rows: list[Standing]


class MetricsProps(BaseModel, extra="forbid", strict=True):
    title: Literal["Team metrics"]
    columns: list[Column]
    rows: list[TeamMetrics]


class PageElement(BaseModel, extra="forbid", strict=True):
    type: Literal["Page"]
    props: PageProps
    children: list[str]


class TextElement(BaseModel, extra="forbid", strict=True):
    type: Literal["Text"]
    props: TextProps
    children: list[str] = Field(max_length=0)


class TableElement(BaseModel, extra="forbid", strict=True):
    type: Literal["Table"]
    props: Annotated[StandingsProps | MetricsProps, Field(discriminator="title")]
    children: list[str] = Field(max_length=0)


class PageSpec(BaseModel, extra="forbid", strict=True):
    root: Literal["page"]
    elements: dict[
        str,
        Annotated[
            PageElement | TextElement | TableElement, Field(discriminator="type")
        ],
    ]
