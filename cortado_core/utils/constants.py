from enum import Enum

BARROW = "\u2191"
FARROW = "\u2193"
SKIP = ">>"
SILENT_TRANSITION = "\u03C4"

ARTIFICAL_START_NAME = "CT_ARTIFICAL_START_NAME"
ARTIFICAL_END_NAME = "CT_ARTIFICAL_END_NAME"


class PartialOrderMode(Enum):
    NONE = "none"
    CLOSURE = "closure"
    REDUCTION = "reduction"


class DependencyTypes(Enum):
    LOG = "l"
    MODEL = "m"
    INDECISIVE = "i"
    SYNCHRONOUS = "s"
