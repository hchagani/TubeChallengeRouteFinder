from datetime import datetime, timezone
from functools import partial
from typing import Optional

from sqlalchemy import Enum as SAEnum
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.engine.default import DefaultExecutionContext
from sqlalchemy.orm import declarative_base, mapped_column, relationship, Mapped

from tubechallenge.db.constants import (
    MAX_LINE_ID_LENGTH,
    MAX_STATION_ID_LENGTH,
)
from tubechallenge.db.enums import BranchDirection, ModeOfTransport, StatusFlag

Base = declarative_base()


def get_date_created(context: DefaultExecutionContext) -> datetime:
    """Get value of date_created field to fill last_updated field."""
    return context.get_current_parameters()["date_created"]


class BaseModel(Base):
    """Base for all database models. Contains fields common to all models."""
    __abstract__ = True

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    date_created: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=partial(datetime.now, tz=timezone.utc)
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=get_date_created,
        onupdate=partial(datetime.now, tz=timezone.utc),
    )


class Graph(BaseModel):
    """Database model to store metadata for database."""
    __tablename__ = "graph"

    status: Mapped[StatusFlag] = mapped_column(
        SAEnum(StatusFlag, name="graph_status"),
        nullable=False,
        default=StatusFlag.PENDING,
    )


class Line(BaseModel):
    """Database model for tube lines."""
    __tablename__ = "lines"

    line_id: Mapped[str] = mapped_column(
        String(MAX_LINE_ID_LENGTH), nullable=False, index=True, unique=True
    )  # TfL's ID
    name: Mapped[str]
    mode: Mapped[ModeOfTransport] = mapped_column(
        SAEnum(ModeOfTransport, name="modeoftransport", validate_strings=True),
        nullable=False,
    )
    average_speed: Mapped[float] = mapped_column(default=0.0)
    branches: Mapped[Optional[list["Branch"]]] = relationship(
        back_populates="line", lazy="selectin"
    )
    connections: Mapped[Optional[list["Connection"]]] = relationship(
        back_populates="line", lazy="selectin"
    )


class Branch(BaseModel):
    """Database model for tube line branches."""
    __tablename__ = "branches"

    name: Mapped[str]
    line_id: Mapped[int] = mapped_column(ForeignKey("lines.id"))
    line: Mapped[Line] = relationship(back_populates="branches")
    direction: Mapped[BranchDirection] = mapped_column(
        SAEnum(BranchDirection, name="branchdirection", validate_strings=True),
        nullable=False,
    )
    branchstations: Mapped[Optional[list["BranchStation"]]] = relationship(
        back_populates="branch", lazy="selectin"
    )


class Station(BaseModel):
    """Database model for statons."""
    __tablename__ = "stations"

    station_id: Mapped[str] = mapped_column(
        String(MAX_STATION_ID_LENGTH), nullable=False, index=True, unique=True
    )
    name: Mapped[str]
    zone: Mapped[str]
    latitude: Mapped[float] = mapped_column(index=True)
    longitude: Mapped[float] = mapped_column(index=True)
    is_open: Mapped[bool] = mapped_column(default=True)
    journeymatrixstations: Mapped[Optional[list["JourneyMatrixStation"]]] = relationship(
        back_populates="station", lazy="selectin"
    )
    branchstations: Mapped[Optional[list["BranchStation"]]] = relationship(
        back_populates="station", lazy="selectin"
    )
    connections_from: Mapped[Optional[list["Connection"]]] = relationship(
        back_populates="from_station",
        foreign_keys="[Connection.from_station_id]",
        lazy="selectin",
    )
    connections_to: Mapped[Optional[list["Connection"]]] = relationship(
        back_populates="to_station",
        foreign_keys="[Connection.to_station_id]",
        lazy="selectin",
    )


class BranchStation(BaseModel):
    """Database model for ordered sequence of stations along a branch."""
    __tablename__ = "branch_stations"

    branch_id: Mapped[int] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE")
    )
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE")
    )
    sequence: Mapped[int]
    branch: Mapped[Branch] = relationship(back_populates="branchstations")
    station: Mapped[Station] = relationship(back_populates="branchstations")


class Connection(Base):
    """Database model for connections between adjacent stations."""
    __tablename__ = "connections"

    from_station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), primary_key=True
    )
    to_station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE"), primary_key=True
    )
    line_id: Mapped[int] = mapped_column(
        ForeignKey("lines.id", ondelete="CASCADE"), primary_key=True
    )
    time: Mapped[int]  # travel time in minutes
    interval: Mapped[int]  # mean time between trains in minutes
    distance: Mapped[float] = mapped_column(default=0.0)  # distance in metres
    active: Mapped[bool] = mapped_column(default=True)
    from_station: Mapped[Station] = relationship(
        back_populates="connections_from",
        foreign_keys=[from_station_id],
    )
    to_station: Mapped[Station] = relationship(
        back_populates="connections_to",
        foreign_keys=[to_station_id],
    )
    line: Mapped[Line] = relationship(back_populates="connections")
