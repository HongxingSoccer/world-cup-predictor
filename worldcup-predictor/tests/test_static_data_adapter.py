"""Unit tests for `StaticDataAdapter`."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.adapters.base import AdapterMethodNotSupported
from src.adapters.static_data import StaticDataAdapter

_SAMPLE_CSV = (
    "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
    "1872-11-30,Scotland,England,0,0,Friendly,Glasgow,Scotland,FALSE\n"
    "1980-06-11,Italy,Spain,0,0,UEFA Euro,Milan,Italy,FALSE\n"
    "2026-06-15,USA,Mexico,2,1,FIFA World Cup,New York,United States,TRUE\n"
)


@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    path = tmp_path / "results.csv"
    path.write_text(_SAMPLE_CSV, encoding="utf-8")
    return path


@pytest.mark.asyncio
async def test_fetch_matches_filters_to_target_year(sample_csv: Path) -> None:
    adapter = StaticDataAdapter(csv_url=str(sample_csv))
    try:
        matches = await adapter.fetch_matches(2026)
    finally:
        await adapter.aclose()

    assert len(matches) == 1
    assert matches[0].home_team_name == "USA"
    assert matches[0].competition_name == "FIFA World Cup"
    assert matches[0].status == "finished"
    assert matches[0].home_score == 2 and matches[0].away_score == 1


@pytest.mark.asyncio
async def test_fetch_matches_all_returns_every_row(sample_csv: Path) -> None:
    adapter = StaticDataAdapter(csv_url=str(sample_csv))
    try:
        matches = await adapter.fetch_matches("all")
    finally:
        await adapter.aclose()

    assert len(matches) == 3


@pytest.mark.asyncio
async def test_fetch_matches_synthetic_id_is_stable_across_runs(sample_csv: Path) -> None:
    adapter = StaticDataAdapter(csv_url=str(sample_csv))
    try:
        first = await adapter.fetch_matches(2026)
        second = await adapter.fetch_matches(2026)
    finally:
        await adapter.aclose()

    assert first[0].external_id == second[0].external_id
    assert first[0].external_id.startswith("2026-06-15")


@pytest.mark.asyncio
async def test_match_detail_raises_method_not_supported(sample_csv: Path) -> None:
    adapter = StaticDataAdapter(csv_url=str(sample_csv))
    try:
        with pytest.raises(AdapterMethodNotSupported):
            await adapter.fetch_match_detail(1)
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_health_check_returns_true_for_readable_csv(sample_csv: Path) -> None:
    adapter = StaticDataAdapter(csv_url=str(sample_csv))
    try:
        assert await adapter.health_check() is True
    finally:
        await adapter.aclose()
