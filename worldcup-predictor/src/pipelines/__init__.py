"""ETL pipelines that turn adapter DTOs into rows in core tables."""
from .base import BasePipeline, PipelineResult
from .match_pipeline import MatchPipeline
from .odds_pipeline import OddsPipeline
from .player_pipeline import PlayerPipeline
from .stats_pipeline import StatsPipeline

__all__ = [
    "BasePipeline",
    "MatchPipeline",
    "OddsPipeline",
    "PipelineResult",
    "PlayerPipeline",
    "StatsPipeline",
]
