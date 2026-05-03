"""Feature-engineering layer (Phase 2 v1, 28 features in 6 groups)."""
from .attack_defense import AttackDefenseFeatures
from .base import BaseFeatureCalculator, FeatureDict, MatchContext
from .elo import EloFeatures
from .h2h import H2HFeatures
from .home_away import HomeAwayFeatures
from .pipeline import DEFAULT_FEATURE_VERSION, FeaturePipeline
from .recent_form import RecentFormFeatures
from .team_strength import TeamStrengthFeatures

__all__ = [
    "AttackDefenseFeatures",
    "BaseFeatureCalculator",
    "DEFAULT_FEATURE_VERSION",
    "EloFeatures",
    "FeatureDict",
    "FeaturePipeline",
    "H2HFeatures",
    "HomeAwayFeatures",
    "MatchContext",
    "RecentFormFeatures",
    "TeamStrengthFeatures",
]
