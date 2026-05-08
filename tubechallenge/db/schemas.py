from pydantic import BaseModel, constr
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
    graph_id: int


class UpdateGraph(BaseModel):
    name: Optional[str] = None
    status: Optional[StatusFlag] = None


class UpdateJob(BaseModel):
    status: Optional[StatusFlag] = None
    progress: Optional[float] = None
    error_message: Optional[str] = None
