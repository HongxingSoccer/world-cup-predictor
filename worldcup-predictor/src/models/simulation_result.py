"""simulation_results — Monte Carlo tournament-simulation snapshots (Phase 4).

Schema follows ``docs/design/06_Phase4_ModelEvolution.md §6.4``: a single
JSONB ``results`` blob holds every per-stage probability for every team
(group_advance_prob, round_of_16_prob, …, champion_prob, most_likely_bracket).
Frontend reads only the latest row per ``simulation_version``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    simulation_version: Mapped[str] = mapped_column(String(30), nullable=False)
    num_simulations: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="10000"
    )
    model_version: Mapped[str] = mapped_column(String(30), nullable=False)
    results: Mapped[Any] = mapped_column(JSONB, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("idx_simulation_latest", "computed_at"),)
