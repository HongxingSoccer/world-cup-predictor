"""HTML backtest report — Jinja2 template + matplotlib charts (base64-embedded).

`generate_html_report(...)` returns a fully-rendered HTML string. The
`scripts/run_backtest.py` driver writes that to disk and (optionally) logs
it as an MLflow artifact.

Charts:
    * `cumulative_pl_chart` — cumulative ROI curve over the test horizon.
    * `calibration_chart`   — predicted-vs-observed home-win rate.
"""
from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # noqa: E402 — must precede pyplot import in headless contexts
import matplotlib.pyplot as plt  # noqa: E402
from jinja2 import Template  # noqa: E402

from src.ml.backtest.evaluator import BacktestMetrics  # noqa: E402
from src.ml.backtest.runner import BacktestSample  # noqa: E402

# Concise template — one logical block per spec section. Inline CSS so the
# output works as an email attachment / standalone artifact.
_REPORT_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>WCP Backtest — {{ model_version }} — {{ generated_at }}</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; color: #222; }
h1, h2 { border-bottom: 1px solid #ddd; padding-bottom: 4px; }
table { border-collapse: collapse; margin: 12px 0; }
th, td { padding: 6px 12px; border: 1px solid #ddd; text-align: right; }
th:first-child, td:first-child { text-align: left; }
.kpi { display: inline-block; min-width: 180px; margin: 8px; padding: 12px;
       background: #f5f7fa; border-left: 4px solid #4a90e2; }
.kpi-label { font-size: 12px; text-transform: uppercase; color: #888; }
.kpi-value { font-size: 24px; font-weight: 600; }
.chart { margin: 16px 0; }
</style></head><body>

<h1>WCP Backtest Report</h1>
<p>
  <strong>Model:</strong> {{ model_version }} &middot;
  <strong>Feature version:</strong> {{ feature_version }} &middot;
  <strong>Window:</strong> {{ window }} &middot;
  <strong>Generated:</strong> {{ generated_at }}
</p>

<h2>Executive Summary</h2>
<div>
  <div class="kpi"><div class="kpi-label">Samples</div><div class="kpi-value">{{ metrics.n_samples }}</div></div>
  <div class="kpi"><div class="kpi-label">Accuracy</div><div class="kpi-value">{{ pct(metrics.accuracy) }}</div></div>
  <div class="kpi"><div class="kpi-label">Brier</div><div class="kpi-value">{{ "%.4f"|format(metrics.brier_score) }}</div></div>
  <div class="kpi"><div class="kpi-label">ROI (all)</div><div class="kpi-value">{{ pct(metrics.roi_all) }}</div></div>
  <div class="kpi"><div class="kpi-label">ROI (+EV)</div><div class="kpi-value">{{ pct(metrics.roi_positive_ev) }}</div></div>
  <div class="kpi"><div class="kpi-label">+EV hit-rate</div><div class="kpi-value">{{ pct(metrics.positive_ev_hit_rate) }}</div></div>
</div>

<h2>Cumulative P&amp;L (positive-EV stake-1)</h2>
<div class="chart"><img src="data:image/png;base64,{{ cumulative_chart_b64 }}" alt="Cumulative P&L"></div>

<h2>Probability calibration</h2>
<div class="chart"><img src="data:image/png;base64,{{ calibration_chart_b64 }}" alt="Calibration curve"></div>

<h2>ROI by market</h2>
<table>
  <tr><th>Market</th><th>ROI</th></tr>
  {% for market, roi in metrics.roi_by_market.items() %}
  <tr><td>{{ market }}</td><td>{{ pct(roi) }}</td></tr>
  {% endfor %}
</table>

<h2>Streaks &amp; drawdown</h2>
<table>
  <tr><th>Metric</th><th>Value</th></tr>
  <tr><td>Max drawdown (units)</td><td>{{ "%.2f"|format(metrics.max_drawdown) }}</td></tr>
  <tr><td>Longest winning streak</td><td>{{ metrics.longest_winning_streak }}</td></tr>
  <tr><td>Longest losing streak</td><td>{{ metrics.longest_losing_streak }}</td></tr>
</table>

{% if baseline_table %}
<h2>Baseline comparison</h2>
<table>
  <tr><th>Model</th><th>Accuracy</th><th>Brier</th><th>ROI (all)</th><th>ROI (+EV)</th></tr>
  {% for row in baseline_table %}
  <tr>
    <td>{{ row.model }}</td>
    <td>{{ pct(row.accuracy) }}</td>
    <td>{{ "%.4f"|format(row.brier) }}</td>
    <td>{{ pct(row.roi_all) }}</td>
    <td>{{ pct(row.roi_positive_ev) }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

<h2>Conclusions</h2>
<p>{{ conclusion or "No automated conclusion generated." }}</p>

</body></html>
"""


def generate_html_report(
    *,
    model_version: str,
    feature_version: str,
    window: str,
    samples: list[BacktestSample],
    metrics: BacktestMetrics,
    baseline_metrics: dict[str, BacktestMetrics] | None = None,
    conclusion: str | None = None,
) -> str:
    """Render the HTML report to a string. Caller writes it to disk."""
    template = Template(_REPORT_TEMPLATE)
    return template.render(
        model_version=model_version,
        feature_version=feature_version,
        window=window,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        metrics=metrics,
        cumulative_chart_b64=_cumulative_pl_chart(samples),
        calibration_chart_b64=_calibration_chart(metrics),
        baseline_table=_baseline_rows(baseline_metrics) if baseline_metrics else None,
        conclusion=conclusion,
        pct=lambda x: f"{x * 100:+.2f}%",
    )


def write_html_report(html: str, target: str | Path) -> Path:
    """Write `html` to `target` (creating parent dirs) and return the path."""
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


# --- Charts → base64 PNG ---------------------------------------------------


def _cumulative_pl_chart(samples: list[BacktestSample]) -> str:
    if not samples:
        return _png_b64(_empty_chart("no samples"))
    # Build a cumulative P&L from the same bet definition the evaluator uses
    # (best-EV outcome, stake 1) — defensive duplication keeps the chart
    # standalone if the evaluator changes shape later.
    from src.ml.backtest.evaluator import _positive_ev_pls

    pls = _positive_ev_pls(samples)
    if not pls:
        return _png_b64(_empty_chart("no positive-EV bets"))
    cumulative = []
    running = 0.0
    for pl in pls:
        running += pl
        cumulative.append(running)
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.plot(range(1, len(cumulative) + 1), cumulative, color="#4a90e2", linewidth=2)
    ax.axhline(0, color="#aaa", linewidth=0.5)
    ax.set_title("Cumulative P&L (units)")
    ax.set_xlabel("Bet #")
    ax.set_ylabel("Cumulative P&L")
    ax.grid(True, linestyle="--", alpha=0.5)
    return _png_b64(fig)


def _calibration_chart(metrics: BacktestMetrics) -> str:
    buckets = metrics.calibration_curve
    if not buckets:
        return _png_b64(_empty_chart("no calibration data"))
    xs = [b["avg_predicted"] for b in buckets]
    ys = [b["observed_rate"] for b in buckets]
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], color="#bbb", linestyle="--", linewidth=1)
    ax.scatter(xs, ys, color="#e94e77", zorder=3)
    ax.set_xlabel("Mean predicted P(home win)")
    ax.set_ylabel("Observed P(home win)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("Calibration: predicted vs observed home-win rate")
    ax.grid(True, linestyle="--", alpha=0.5)
    return _png_b64(fig)


def _empty_chart(message: str):  # type: ignore[no-untyped-def]
    fig, ax = plt.subplots(figsize=(6, 2.5))
    ax.text(0.5, 0.5, message, ha="center", va="center", color="#888", fontsize=14)
    ax.set_axis_off()
    return fig


def _png_b64(fig: Any) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _baseline_rows(
    baseline_metrics: dict[str, BacktestMetrics],
) -> list[dict[str, Any]]:
    return [
        {
            "model": name,
            "accuracy": metrics.accuracy,
            "brier": metrics.brier_score,
            "roi_all": metrics.roi_all,
            "roi_positive_ev": metrics.roi_positive_ev,
        }
        for name, metrics in baseline_metrics.items()
    ]
