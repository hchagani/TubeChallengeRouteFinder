from pydantic import BaseModel, constr, field_validator, model_validator
from typing import Optional

from tubechallenge.db.constants import MAX_LINE_ID_LENGTH, MAX_STATION_ID_LENGTH
from tubechallenge.db.enums import (
    BranchDirection,
    JobType,
    ModeOfTransport,
    StatusFlag,
)


class CreateBranchStation(BaseModel):
    station_id: int
    sequence: int
    graph_id: int


class CreateBranch(BaseModel):
    name: str
    line_id: int
    direction: BranchDirection
    graph_id: int
    branchstations: list[CreateBranchStation]


class CreateConnection(BaseModel):
    graph_id: int
    from_station_id: int
    to_station_id: int
    line_id: int
    time: int
    interval: int


class CreateGraph(BaseModel):
    name: Optional[str] = None
    run_pace: Optional[int] = None

    @field_validator("run_pace", mode="before")
    @classmethod
    def parse_run_pace(cls, value):
        if isinstance(value, str):
            try:
                minutes, seconds = map(int, value.split(":"))
            except ValueError:
                raise ValueError("Duration must be in MM:SS format.")

            return minutes * 60 + seconds

        return value


class CreateJob(BaseModel):
    job_type: JobType
    graph_id: int


class CreateLine(BaseModel):
    line_id: constr(max_length=MAX_LINE_ID_LENGTH)
    name: str
    mode: ModeOfTransport
    graph_id: int


class CreateStation(BaseModel):
    station_id: constr(max_length=MAX_STATION_ID_LENGTH)
    name: str
    zone: str
    latitude: float
    longitude: float
    is_tube: bool
    graph_id: int


class CreateStationPair(BaseModel):
    origin_station_id: int
    destination_station_id: int
    graph_id: int

    @model_validator(mode="after")
    def check_stations_are_different(self):
        if self.origin_station_id == self.destination_station_id:
            raise ValueError(
                "Origin and destination stations must be different."
            )

        return self


class UpdateGraph(BaseModel):
    name: Optional[str] = None
    status: Optional[StatusFlag] = None


class UpdateJob(BaseModel):
    status: Optional[StatusFlag] = None
    progress: Optional[float] = None
    error_message: Optional[str] = None
