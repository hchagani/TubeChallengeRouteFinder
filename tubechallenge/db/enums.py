from enum import Enum


class BranchDirection(str, Enum):
    """Direction of tube branch."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class JobType(str, Enum):
    ROUTE_GENERATION = "route_generation"
    FIND_SOLUTION = "find_solution"


class StatusFlag(str, Enum):
    """Status of job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ModeOfTransport(str, Enum):
    """Mode of transport represented by a line."""

    TUBE = "tube"
    FOOT = "foot"
