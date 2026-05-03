"""team_name_aliases — many-to-one map of source-specific team names → canonical team_id.

Used by the entity-resolution layer to recognize "Man Utd", "Manchester United",
"曼联" etc. as the same team across different scraped sources.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TeamNameAlias(Base):
    __tablename__ = "team_name_aliases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    # 'api_football' | 'transfermarkt' | 'fbref' | 'odds_api' | 'manual' | ...
    source: Mapped[str] = mapped_column(String(30), nullable=False)

    __table_args__ = (
        UniqueConstraint("alias", "source", name="uq_team_alias_source"),
    )
