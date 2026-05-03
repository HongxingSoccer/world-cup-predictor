"""Team-name resolution across data sources.

Different providers spell the same team differently ("Man Utd",
"Manchester United", "曼联"). `TeamNameMapper` keeps an in-process cache of the
`team_name_aliases` table for O(1) exact lookups and falls back to rapidfuzz
for the long tail. New aliases discovered at ingest time can be persisted via
`add_alias()` so the next run resolves them exactly.
"""
from __future__ import annotations

import re

import structlog
from rapidfuzz import fuzz, process
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.models.team import Team
from src.models.team_name_alias import TeamNameAlias

logger = structlog.get_logger(__name__)

# Strip non-letter / non-digit characters, lowercase. Used to make
# "Man. Utd" / "man utd" / "MAN-UTD" all collide on the same lookup key.
_NORMALIZE_RE = re.compile(r"[^\w]+", flags=re.UNICODE)


def _normalize(name: str) -> str:
    """Lower-case and strip punctuation/whitespace for cache-key lookups."""
    return _NORMALIZE_RE.sub("", name).lower().strip()


class TeamNameMapper:
    """Maps source-specific team names to canonical `teams.id`.

    Resolution order:
        1. Exact match against `(alias, source)` in `team_name_aliases`.
        2. Exact match against `(canonical_name, *)` in `teams`.
        3. Fuzzy match (rapidfuzz token-set ratio) above `threshold`.

    Callers should prefer instantiating once per ingest run and reusing the
    mapper, since `_load()` issues two queries against the catalog tables.

    Attributes:
        DEFAULT_FUZZY_THRESHOLD: rapidfuzz score (0–100) below which fuzzy
            matches are rejected. Default 85 — empirically high enough to
            avoid false positives on similarly-named teams (e.g. "Real Madrid"
            vs "Real Madrid B").
    """

    DEFAULT_FUZZY_THRESHOLD: int = 85

    def __init__(
        self,
        session: Session,
        *,
        threshold: int = DEFAULT_FUZZY_THRESHOLD,
    ) -> None:
        self._session = session
        self._threshold = threshold
        # (normalized_alias, source) -> team_id
        self._alias_index: dict[tuple[str, str], int] = {}
        # normalized_canonical_name -> team_id
        self._canonical_index: dict[str, int] = {}
        # team_id -> canonical_name (used for fuzzy candidate set)
        self._canonical_names: dict[int, str] = {}
        self._load()

    # --- Public methods ---

    def resolve(self, name: str, source: str) -> int | None:
        """Resolve a raw name to a `teams.id`, or None if unmatched.

        Args:
            name: Raw team name as it appeared in the source.
            source: Source identifier (e.g. ``"api_football"``, ``"fbref"``).

        Returns:
            The matched canonical team id, or None if neither exact nor fuzzy
            resolution succeeds.
        """
        norm = _normalize(name)
        if not norm:
            return None

        if (team_id := self._alias_index.get((norm, source))) is not None:
            return team_id
        if (team_id := self._canonical_index.get(norm)) is not None:
            return team_id
        return self.fuzzy_match(name, source)

    def fuzzy_match(self, name: str, source: str) -> int | None:
        """Return the best fuzzy candidate above `self._threshold`, else None."""
        if not self._canonical_names:
            return None

        candidates = list(self._canonical_names.items())
        choices = {team_id: canonical for team_id, canonical in candidates}
        best = process.extractOne(
            query=name,
            choices=choices,
            scorer=fuzz.token_set_ratio,
            score_cutoff=self._threshold,
        )
        if best is None:
            return None
        _, score, team_id = best
        logger.debug(
            "team_name_fuzzy_match",
            input=name,
            source=source,
            matched_team_id=team_id,
            score=score,
        )
        return int(team_id)

    def add_alias(self, team_id: int, alias: str, source: str) -> None:
        """Persist a new alias and update the in-memory cache.

        Uses ``ON CONFLICT DO NOTHING`` on `(alias, source)` so concurrent
        ingest runs don't error out on the unique constraint.
        """
        stmt = (
            pg_insert(TeamNameAlias)
            .values(team_id=team_id, alias=alias, source=source)
            .on_conflict_do_nothing(index_elements=["alias", "source"])
        )
        self._session.execute(stmt)
        self._alias_index[(_normalize(alias), source)] = team_id

    # --- Private methods ---

    def _load(self) -> None:
        team_rows = self._session.execute(select(Team.id, Team.name)).all()
        for team_id, name in team_rows:
            self._canonical_names[team_id] = name
            self._canonical_index[_normalize(name)] = team_id

        alias_rows = self._session.execute(
            select(TeamNameAlias.team_id, TeamNameAlias.alias, TeamNameAlias.source)
        ).all()
        for team_id, alias, source in alias_rows:
            self._alias_index[(_normalize(alias), source)] = team_id

        logger.debug(
            "team_name_mapper_loaded",
            teams=len(self._canonical_names),
            aliases=len(self._alias_index),
        )
