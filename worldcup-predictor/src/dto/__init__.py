"""Data-transfer objects shared between adapters, pipelines, and tasks.

DTOs are immutable Pydantic v2 models — they carry data across module
boundaries without any DB or framework coupling. ORM models (in `src.models`)
are *not* DTOs and must not cross those boundaries.
"""
from .match import MatchDTO
from .odds import ALLOWED_OUTCOME_KEYS, OddsDTO
from .player import InjuryDTO, PlayerDTO, PlayerStatDTO, ValuationDTO
from .stats import MatchDetailDTO, MatchStatsDTO, TeamStatsDTO

__all__ = [
    "ALLOWED_OUTCOME_KEYS",
    "InjuryDTO",
    "MatchDTO",
    "MatchDetailDTO",
    "MatchStatsDTO",
    "OddsDTO",
    "PlayerDTO",
    "PlayerStatDTO",
    "TeamStatsDTO",
    "ValuationDTO",
]
