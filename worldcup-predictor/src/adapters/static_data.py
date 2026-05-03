"""Static-CSV adapter for public datasets (e.g. martj42/international_results).

Used as a one-shot historical backfill — typically the very first ingest run
for a fresh database — to populate `matches` / `h2h_records` for years that
predate API coverage. After backfill the tables are kept current by the live
adapters.

Source CSV is fetched once over HTTPS and parsed in-memory. The default URL
points at the canonical raw GitHub blob, but any HTTP(S) URL or local
``file://`` URL works (useful for offline tests).
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog

from src.adapters.base import (
    AdapterMethodNotSupported,
    BaseDataSourceAdapter,
    DataFetchError,
)
from src.dto.match import MatchDTO
from src.dto.player import PlayerStatDTO
from src.dto.stats import MatchDetailDTO, TeamStatsDTO
from src.utils.rate_limiter import RateLimitConfig

logger = structlog.get_logger(__name__)

SOURCE_NAME: str = "static_data"
DEFAULT_INTERNATIONAL_RESULTS_URL: str = (
    "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
)


class StaticDataAdapter(BaseDataSourceAdapter):
    """Loader for one-shot CSV datasets.

    Only `fetch_matches` is meaningful here; everything else raises
    `AdapterMethodNotSupported`. `season_id` is interpreted as the four-digit
    year to slice from the CSV; pass `season_id="all"` to ingest every row.
    """

    DEFAULT_RATE_LIMIT: RateLimitConfig = RateLimitConfig(
        requests_per_second=10.0,  # Local file / cached CDN — rate is irrelevant.
        burst_size=10,
    )

    # Required CSV columns from martj42/international_results.
    REQUIRED_COLUMNS: frozenset[str] = frozenset(
        {"date", "home_team", "away_team", "home_score", "away_score", "tournament"}
    )

    def __init__(
        self,
        *,
        csv_url: str = DEFAULT_INTERNATIONAL_RESULTS_URL,
        rate_limit: RateLimitConfig | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            SOURCE_NAME,
            rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT,
            **kwargs,
        )
        self._csv_url = csv_url

    # --- Public API ---

    def get_rate_limit(self) -> RateLimitConfig:
        return self.DEFAULT_RATE_LIMIT

    async def health_check(self) -> bool:
        try:
            text = await self._read_csv_text()
        except (DataFetchError, OSError, httpx.HTTPError):
            return False
        return bool(text.strip())

    async def fetch_matches(self, season_id: str | int) -> list[MatchDTO]:
        text = await self._read_csv_text()
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames is None or not self.REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise DataFetchError(
                SOURCE_NAME,
                f"Missing required columns; got {reader.fieldnames}",
            )

        target_year = self._parse_target_year(season_id)
        out: list[MatchDTO] = []
        for row in reader:
            match_date = self._parse_iso_date(row["date"])
            if target_year is not None and match_date.year != target_year:
                continue
            try:
                out.append(self._row_to_match_dto(row, match_date))
            except (KeyError, ValueError) as exc:
                self._log.warning("static_row_skipped", error=str(exc), row=row)
        return out

    async def fetch_match_detail(self, match_id: str | int) -> MatchDetailDTO:
        raise AdapterMethodNotSupported(
            "StaticDataAdapter does not provide per-match detail beyond the row"
        )

    async def fetch_team_stats(
        self, team_id: str | int, season_id: str | int
    ) -> TeamStatsDTO:
        raise AdapterMethodNotSupported(
            "StaticDataAdapter does not provide team-level stats"
        )

    async def fetch_player_stats(self, match_id: str | int) -> list[PlayerStatDTO]:
        raise AdapterMethodNotSupported(
            "StaticDataAdapter does not provide player stats"
        )

    # --- Internal ---

    async def _read_csv_text(self) -> str:
        if self._csv_url.startswith(("http://", "https://")):
            response = await self._request_with_retry(self._csv_url)
            return response.text
        if self._csv_url.startswith("file://"):
            local = Path(self._csv_url[len("file://") :])
            return local.read_text(encoding="utf-8")
        # Bare local path is permitted for tests / scripts.
        return Path(self._csv_url).read_text(encoding="utf-8")

    @staticmethod
    def _parse_target_year(season_id: str | int) -> int | None:
        if isinstance(season_id, int):
            return season_id
        if season_id.lower() == "all":
            return None
        return int(season_id)

    @staticmethod
    def _parse_iso_date(raw: str) -> datetime:
        # CSV dates are pure YYYY-MM-DD; we anchor at 00:00 UTC since the data
        # has no kickoff time.
        parts = raw.split("-")
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        return datetime.combine(
            datetime(year, month, day).date(),
            time.min,
            tzinfo=timezone.utc,
        )

    def _row_to_match_dto(self, row: dict[str, str], match_date: datetime) -> MatchDTO:
        home_score = _maybe_int(row.get("home_score"))
        away_score = _maybe_int(row.get("away_score"))
        # martj42 dataset: every row is a finished international friendly /
        # tournament match, so status is always 'finished'.
        return MatchDTO(
            external_id=self._synthetic_external_id(row, match_date),
            home_team_name=row["home_team"],
            away_team_name=row["away_team"],
            match_date=match_date,
            status="finished",
            home_score=home_score,
            away_score=away_score,
            venue=row.get("city") or None,
            round=None,
            competition_name=row["tournament"],
            season_year=match_date.year,
        )

    @staticmethod
    def _synthetic_external_id(row: dict[str, str], match_date: datetime) -> str:
        # CSV has no native id; build a stable composite so re-runs upsert
        # rather than duplicate.
        return (
            f"{match_date.date().isoformat()}:"
            f"{row['home_team']}:{row['away_team']}:{row['tournament']}"
        )


def _maybe_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
