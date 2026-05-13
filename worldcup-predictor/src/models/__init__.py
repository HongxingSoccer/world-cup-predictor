"""SQLAlchemy ORM models.

Importing this package registers every table on `Base.metadata`, which is what
Alembic's autogeneration target reads. Add new models here when introduced.
"""
from .analysis_report import AnalysisReport
from .base import Base, TimestampMixin
from .competition import Competition
from .data_source_log import DataSourceLog
from .elo_rating import EloRating
from .h2h_record import H2HRecord
from .hedge_scenario import HedgeCalculation, HedgeResult, HedgeScenario, ParlayLeg
from .injury import Injury
from .match import Match
from .match_feature import MatchFeature
from .match_lineup import MatchLineup
from .match_stats import MatchStats
from .odds_analysis import OddsAnalysis
from .odds_snapshot import OddsSnapshot
from .payment import Payment
from .player import Player
from .player_stats import PlayerStats
from .player_valuation import PlayerValuation
from .prediction import Prediction
from .prediction_result import PredictionResult
from .push import PushNotification, UserPushSettings
from .season import Season
from .share_card import ShareCard
from .share_link import ShareLink
from .simulation_result import SimulationResult
from .subscription import Subscription
from .team import Team
from .team_name_alias import TeamNameAlias
from .track_record_stat import TrackRecordStat
from .user import User
from .user_favorite import UserFavorite
from .user_oauth import UserOAuth

__all__ = [
    "AnalysisReport",
    "Base",
    "Competition",
    "DataSourceLog",
    "EloRating",
    "H2HRecord",
    "HedgeCalculation",
    "HedgeResult",
    "HedgeScenario",
    "Injury",
    "Match",
    "MatchFeature",
    "MatchLineup",
    "MatchStats",
    "OddsAnalysis",
    "OddsSnapshot",
    "ParlayLeg",
    "Payment",
    "Player",
    "PlayerStats",
    "PlayerValuation",
    "Prediction",
    "PredictionResult",
    "PushNotification",
    "Season",
    "ShareCard",
    "ShareLink",
    "SimulationResult",
    "Subscription",
    "Team",
    "TeamNameAlias",
    "TimestampMixin",
    "TrackRecordStat",
    "User",
    "UserFavorite",
    "UserOAuth",
    "UserPushSettings",
]
