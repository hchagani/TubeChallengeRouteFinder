from datetime import datetime, timezone
from functools import partial

from sqlalchemy import Enum as SAEnum
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.engine.default import DefaultExecutionContext
from sqlalchemy.orm import declarative_base, mapped_column, relationship, Mapped

from tubechallenge.db.constants import (
    MAX_LINE_ID_LENGTH,
    MAX_STATION_ID_LENGTH,
)
from tubechallenge.db.enums import (
    BranchDirection,
    JobType,
    ModeOfTransport,
    StatusFlag,
)

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
    lines: Mapped[list["Line"]] = relationship(
        back_populates="graph", lazy="selectin", cascade="all, delete-orphan"
    )
    branches: Mapped[list["Branch"]] = relationship(
        back_populates="graph", lazy="selectin", cascade="all, delete-orphan"
    )
    stations: Mapped[list["Station"]] = relationship(
        back_populates="graph", lazy="selectin", cascade="all, delete-orphan"
    )
    branchstations: Mapped[list["BranchStation"]] = relationship(
        back_populates="graph", lazy="selectin", cascade="all, delete-orphan"
    )
    connections: Mapped[list["Connection"]] = relationship(
        back_populates="graph", lazy="selectin", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="graph", lazy="select", cascade="all, delete-orphan"
    )
    station_pairs: Mapped[list["StationPair"]] = relationship(
        back_populates="graph", lazy="selectin", cascade="all, delete-orphan"
    )
    routes: Mapped[list["Route"]] = relationship(
        back_populates="graph", lazy="selectin", cascade="all, delete-orphan"
    )
    segments: Mapped[list["RouteSegment"]] = relationship(
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
    graph_id: Mapped[int] = mapped_column(
        ForeignKey("graphs.id"), nullable=False
    )
    graph: Mapped[Graph] = relationship(back_populates="lines")
    branches: Mapped[list["Branch"]] = relationship(
        back_populates="line", lazy="selectin"
    )
    connections: Mapped[list["Connection"]] = relationship(
        back_populates="line", lazy="selectin"
    )
    segments: Mapped[list["RouteSegment"]] = relationship(
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
    branchstations: Mapped[list["BranchStation"]] = relationship(
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
    branchstations: Mapped[list["BranchStation"]] = relationship(
        back_populates="station", lazy="selectin"
    )
    connections_from: Mapped[list["Connection"]] = relationship(
        back_populates="from_station",
        foreign_keys="[Connection.from_station_id]",
        lazy="selectin",
    )
    connections_to: Mapped[list["Connection"]] = relationship(
        back_populates="to_station",
        foreign_keys="[Connection.to_station_id]",
        lazy="selectin",
    )
    route_origins: Mapped[list["StationPair"]] = relationship(
        back_populates="origin_station",
        foreign_keys="[StationPair.origin_station_id]",
        lazy="selectin",
    )
    route_destinations: Mapped[list["StationPair"]] = relationship(
        back_populates="destination_station",
        foreign_keys="[StationPair.destination_station_id]",
        lazy="selectin",
    )
    segments: Mapped[list["RouteSegment"]] = relationship(
        back_populates="station", lazy="selectin"
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


class Job(BaseModel):
    """Database model for background jobs."""
    __tablename__ = "jobs"

    job_type: Mapped[JobType] = mapped_column(SAEnum(
        StatusFlag, name="job_type"), nullable=False
    )
    status: Mapped[StatusFlag] = mapped_column(
        SAEnum(StatusFlag, name="job_status"),
        nullable=False,
        default=StatusFlag.PENDING,
    )
    progress: Mapped[float] = mapped_column(default=0.0)  # [0.0, 1.0]
    error_message: Mapped[str] = mapped_column(nullable=True)
    graph_id: Mapped[int] = mapped_column(
        ForeignKey("graphs.id"), nullable=False
    )
    graph: Mapped[Graph] = relationship(back_populates="jobs")


class StationPair(BaseModel):
    """Database model for station-station pairings."""
    __tablename__ = "station_pairs"
    __table_args__ = (
        UniqueConstraint(
            "origin_station_id",
            "destination_station_id",
            name="uq_origin_destination",
        ),
        Index(
            "idx_origin_destination",
            "origin_station_id",
            "destination_station_id",
        ),
    )

    origin_station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE")
    )
    destination_station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="CASCADE")
    )
    graph_id: Mapped[int] = mapped_column(
        ForeignKey("graphs.id"), nullable=False
    )
    graph: Mapped[Graph] = relationship(back_populates="station_pairs")
    origin_station: Mapped[Station] = relationship(
        back_populates="route_origins", foreign_keys=[origin_station_id]
    )
    destination_station: Mapped[Station] = relationship(
        back_populates="route_destinations",
        foreign_keys=[destination_station_id],
    )
    routes: Mapped[list["Route"]] = relationship(
        back_populates="station_pair", lazy="selectin"
    )


class Route(BaseModel):
    """Database model for possible routes between station pairs."""
    __tablename__ = "routes"

    station_pair_id: Mapped[int] = mapped_column(
        ForeignKey("station_pairs.id"), nullable=False
    )
    duration: Mapped[float]  # total journey time
    tube_short: Mapped[bool]  # route starts with tube train
    tube_end: Mapped[bool]  # route ends with tube train
    graph_id: Mapped[int] = mapped_column(
        ForeignKey("graphs.id"), nullable=False
    )
    graph: Mapped[Graph] = relationship(back_populates="routes")
    station_pair: Mapped[StationPair] = relationship(back_populates="routes")
    segments: Mapped[list["RouteSegment"]] = relationship(
        back_populates="route", lazy="selectin"
    )


class RouteSegment(BaseModel):
    """Database model for segments to recreate routes."""
    __tablename__ = "route_segments"

    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id"), nullable=False
    )
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id"), nullable=False
    )
    line_id: Mapped[int] = mapped_column(
        ForeignKey("lines.id"), nullable=False
    )
    cumulative_time: Mapped[float]  # journey time up and including this segment
    sequence: Mapped[int]
    graph_id: Mapped[int] = mapped_column(
        ForeignKey("graphs.id"), nullable=False
    )
    graph: Mapped[Graph] = relationship(back_populates="segments")
    route: Mapped[Route] = relationship(back_populates="segments")
    station: Mapped[Station] = relationship(back_populates="segments")
    line: Mapped[Line] = relationship(back_populates="segments")
