from pydantic import BaseModel, constr
from typing import Optional

from tubechallenge.db.constants import MAX_LINE_ID_LENGTH, MAX_STATION_ID_LENGTH
from tubechallenge.db.enums import BranchDirection, ModeOfTransport


class CreateBranchStation(BaseModel):
    station_id: int
    sequence: int


class CreateBranch(BaseModel):
    name: str
    line_id: int
    direction: BranchDirection
    branchstations: list[CreateBranchStation]


class CreateConnection(BaseModel):
    from_station_id: int
    to_station_id: int
    line_id: int
    time: int
    interval: int


class CreateLine(BaseModel):
    line_id: constr(max_length=MAX_LINE_ID_LENGTH)
    name: str
    mode: ModeOfTransport


class CreateStation(BaseModel):
    station_id: constr(max_length=MAX_STATION_ID_LENGTH)
    name: str
    zone: str
    latitude: float
    longitude: float
