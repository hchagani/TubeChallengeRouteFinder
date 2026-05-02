from datetime import datetime, timezone
from functools import partial
from typing import Optional

from sqlalchemy import Enum as SAEnum
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
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
    __tablename__ = "graphs"

    name: Mapped[str] = mapped_column(
        String, nullable=False, unique=True
    )  # descriptive name
    status: Mapped[StatusFlag] = mapped_column(
        SAEnum(StatusFlag, name="graph_status"),
        nullable=False,
        default=StatusFlag.PENDING,
    )
    lines: Mapped[Optional[list["Line"]]] = relationship(
        back_populates="graph", lazy="selectin", cascade="all, delete-orphan"
    )
    branches: Mapped[Optional[list["Branch"]]] = relationship(
        back_populates="graph", lazy="selectin", cascade="all, delete-orphan"
    )
    stations: Mapped[Optional[list["Station"]]] = relationship(
        back_populates="graph", lazy="selectin", cascade="all, delete-orphan"
    )
    branchstations: Mapped[Optional[list["BranchStation"]]] = relationship(
        back_populates="graph", lazy="selectin", cascade="all, delete-orphan"
    )
    connections: Mapped[Optional[list["Connection"]]] = relationship(
        back_populates="graph", lazy="selectin", cascade="all, delete-orphan"
    )

class Line(BaseModel):
    """Database model for tube lines."""
    __tablename__ = "lines"
    __table_args__ = (
        UniqueConstraint("graph_id", "line_id", name="uq_graph_line"),
    )

    line_id: Mapped[str] = mapped_column(
        String(MAX_LINE_ID_LENGTH), nullable=False, index=True
    )  # TfL's ID
    name: Mapped[str]
    mode: Mapped[ModeOfTransport] = mapped_column(
        SAEnum(ModeOfTransport, name="modeoftransport", validate_strings=True),
        nullable=False,
    )
    average_speed: Mapped[float] = mapped_column(default=0.0)
    graph_id: Mapped[int] = mapped_column(
        ForeignKey("graphs.id"), nullable=False
    )
    graph: Mapped[Graph] = relationship(back_populates="lines")
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
    graph_id: Mapped[int] = mapped_column(
        ForeignKey("graphs.id"), nullable=False
    )
    graph: Mapped[Graph] = relationship(back_populates="branches")
    branchstations: Mapped[Optional[list["BranchStation"]]] = relationship(
        back_populates="branch", lazy="selectin"
    )


class Station(BaseModel):
    """Database model for statons."""
    __tablename__ = "stations"
    __table_args__ = (
        UniqueConstraint("graph_id", "station_id", name="uq_graph_station"),
    )

    station_id: Mapped[str] = mapped_column(
        String(MAX_STATION_ID_LENGTH), nullable=False, index=True
    )  # TfL's ID
    name: Mapped[str]
    zone: Mapped[str]
    latitude: Mapped[float] = mapped_column(index=True)
    longitude: Mapped[float] = mapped_column(index=True)
    is_open: Mapped[bool] = mapped_column(default=True)
    graph_id: Mapped[int] = mapped_column(
        ForeignKey("graphs.id"), nullable=False
    )
    graph: Mapped[Graph] = relationship(back_populates="stations")
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
    graph_id: Mapped[int] = mapped_column(
        ForeignKey("graphs.id"), nullable=False
    )
    graph: Mapped[Graph] = relationship(back_populates="branchstations")
    branch: Mapped[Branch] = relationship(back_populates="branchstations")
    station: Mapped[Station] = relationship(back_populates="branchstations")


class Connection(Base):
    """Database model for connections between adjacent stations."""
    __tablename__ = "connections"

    graph_id: Mapped[int] = mapped_column(
        ForeignKey("graphs.id", ondelete="CASCADE"), primary_key=True
    )
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
    graph: Mapped[Graph] = relationship(back_populates="connections")
    from_station: Mapped[Station] = relationship(
        back_populates="connections_from",
        foreign_keys=[from_station_id],
    )
    to_station: Mapped[Station] = relationship(
        back_populates="connections_to",
        foreign_keys=[to_station_id],
    )
    line: Mapped[Line] = relationship(back_populates="connections")
