"""SQLAlchemy ORM models.

Importing this package registers every table on `Base.metadata`, which is what
Alembic's autogeneration target reads. Add new models here when introduced.
"""
from .base import Base, TimestampMixin
from .competition import Competition
from .season import Season
from .team import Team
from .player import Player
from .match import Match
from .match_stats import MatchStats
from .match_lineup import MatchLineup
from .player_stats import PlayerStats
from .player_valuation import PlayerValuation
from .injury import Injury
from .odds_snapshot import OddsSnapshot
from .h2h_record import H2HRecord
from .elo_rating import EloRating
from .data_source_log import DataSourceLog
from .match_feature import MatchFeature
from .odds_analysis import OddsAnalysis
from .payment import Payment
from .prediction import Prediction
from .prediction_result import PredictionResult
from .share_card import ShareCard
from .share_link import ShareLink
from .subscription import Subscription
from .team_name_alias import TeamNameAlias
from .track_record_stat import TrackRecordStat
from .user import User
from .user_favorite import UserFavorite
from .user_oauth import UserOAuth
from .analysis_report import AnalysisReport
from .simulation_result import SimulationResult
from .push import PushNotification, UserPushSettings

__all__ = [
    "Base",
    "TimestampMixin",
    "Competition",
    "Season",
    "Team",
    "Player",
    "Match",
    "MatchStats",
    "MatchLineup",
    "PlayerStats",
    "PlayerValuation",
    "Injury",
    "OddsSnapshot",
    "H2HRecord",
    "EloRating",
    "DataSourceLog",
    "MatchFeature",
    "OddsAnalysis",
    "Payment",
    "Prediction",
    "PredictionResult",
    "ShareCard",
    "ShareLink",
    "Subscription",
    "TeamNameAlias",
    "TrackRecordStat",
    "User",
    "UserFavorite",
    "UserOAuth",
    "AnalysisReport",
    "SimulationResult",
    "PushNotification",
    "UserPushSettings",
]
