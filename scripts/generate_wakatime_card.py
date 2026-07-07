#!/usr/bin/env python3
"""Generate a small, aligned WakaTime SVG card for the profile README."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from html import escape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_BASE_URL = "https://api.wakatime.com/api/v1"
DEFAULT_RANGE = "last_7_days"
DEFAULT_OUTPUT = "wakatime.svg"
WIDTH = 640
HEIGHT = 316


DEMO_STATS = {
    "human_readable_total": "15 hrs",
    "human_readable_daily_average": "4 hrs",
    "languages": [
        {"name": "PHP", "percent": 37, "text": "5 hrs 33 mins"},
        {"name": "Go", "percent": 36, "text": "5 hrs 24 mins"},
        {"name": "Markdown", "percent": 22, "text": "3 hrs 18 mins"},
        {"name": "SQL", "percent": 3, "text": "27 mins"},
        {"name": "Bash", "percent": 1, "text": "9 mins"},
    ],
    "editors": [
        {"name": "Claude Code", "percent": 100, "text": "15 hrs"},
    ],
    "operating_systems": [
        {"name": "WSL", "percent": 100, "text": "15 hrs"},
    ],
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="generate deterministic demo data")
    parser.add_argument(
        "--range",
        default=os.environ.get("WAKATIME_RANGE", DEFAULT_RANGE),
        help="WakaTime stats range, for example last_7_days or last_30_days",
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("WAKATIME_OUTPUT", DEFAULT_OUTPUT),
        help="SVG output path",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=int(os.environ.get("WAKATIME_MAX_ATTEMPTS", "8")),
        help="maximum attempts while WakaTime is refreshing cached stats",
    )
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=int(os.environ.get("WAKATIME_RETRY_DELAY", "15")),
        help="seconds to wait between stale WakaTime stats retries",
    )
    args = parser.parse_args()

    stats = DEMO_STATS if args.demo else fetch_stats(args.range, args.max_attempts, args.retry_delay)
    Path(args.output).write_text(render_svg(stats, args.range), encoding="utf-8")
    print(f"Generated {args.output}")
    return 0


def fetch_stats(stats_range: str, max_attempts: int, retry_delay: int) -> dict:
    api_key = os.environ.get("WAKATIME_SECRET")
    if not api_key:
        raise SystemExit("WAKATIME_SECRET is required. Use --demo for local preview data.")

    if max_attempts < 1:
        raise SystemExit("WAKATIME_MAX_ATTEMPTS must be at least 1.")

    token = base64.b64encode(api_key.encode("utf-8")).decode("ascii")

    for attempt in range(1, max_attempts + 1):
        status_code, data = fetch_stats_once(stats_range, token)
        is_up_to_date = data.get("is_up_to_date", True)
        status = data.get("status", "unknown")
        percent = data.get("percent_calculated", "unknown")

        print(
            f"WakaTime stats attempt {attempt}/{max_attempts}: "
            f"http={status_code}, status={status}, percent={percent}, up_to_date={is_up_to_date}"
        )

        if status_code != 202 and is_up_to_date:
            return data

        if attempt < max_attempts:
            time.sleep(retry_delay)

    raise SystemExit("WakaTime stats were still stale after all retry attempts.")


def fetch_stats_once(stats_range: str, token: str) -> tuple[int, dict]:
    request = Request(
        f"{API_BASE_URL}/users/current/stats/{stats_range}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {token}",
            "User-Agent": "igorrochap-profile-readme",
        },
    )

    try:
        with urlopen(request, timeout=20) as response:
            status_code = response.status
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"WakaTime API returned HTTP {error.code}: {body}") from error
    except URLError as error:
        raise SystemExit(f"Could not reach WakaTime API: {error.reason}") from error

    data = payload.get("data")
    if not isinstance(data, dict):
        raise SystemExit("WakaTime API response did not include a data object.")
    return status_code, data


def render_svg(stats: dict, stats_range: str) -> str:
    languages = normalized_items(stats.get("languages", []), 5)
    editors = normalized_items(stats.get("editors", []), 3)
    systems = normalized_items(stats.get("operating_systems", []), 2)
    tools = editors + systems

    total = stats.get("human_readable_total") or format_seconds(stats.get("total_seconds"))
    daily = stats.get("human_readable_daily_average") or format_seconds(stats.get("daily_average"))
    top_language = languages[0] if languages else {"name": "No data", "percent": 0, "text": ""}

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        "  <title id=\"title\">WakaTime coding activity</title>",
        f"  <desc id=\"desc\">Coding activity summary for {escape(human_range(stats_range))}</desc>",
        "  <style>",
        "    .bg{fill:#ffffff}.border{stroke:#d0d7de}.card{fill:#f6f8fa}.title{fill:#0969da}.text{fill:#24292f}.muted{fill:#57606a}.bar-bg{fill:#d8dee4}.bar{fill:#2da44e}",
        "    text{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif}.mono{font-family:ui-monospace,SFMono-Regular,SFMono,Consolas,Liberation Mono,Menlo,monospace}",
        "    @media (prefers-color-scheme: dark){.bg{fill:#0d1117}.border{stroke:#30363d}.card{fill:#161b22}.title{fill:#58a6ff}.text{fill:#c9d1d9}.muted{fill:#8b949e}.bar-bg{fill:#30363d}.bar{fill:#3fb950}}",
        "  </style>",
        f"  <rect class=\"bg border\" x=\"0.5\" y=\"0.5\" width=\"{WIDTH - 1}\" height=\"{HEIGHT - 1}\" rx=\"12\" />",
        "  <text class=\"title\" x=\"28\" y=\"36\" font-size=\"18\" font-weight=\"600\">WakaTime activity</text>",
        f"  <text class=\"muted\" x=\"28\" y=\"58\" font-size=\"12\">{escape(human_range(stats_range))}</text>",
        *summary_card(28, "Total", total),
        *summary_card(226, "Daily average", daily),
        *summary_card(424, "Top language", f"{top_language['name']} {top_language['percent']:.0f}%"),
        *section("Languages", languages, 28, 158, 270),
        *section("Tools", tools, 342, 158, 270),
        "</svg>",
    ]
    return "\n".join(lines) + "\n"


def summary_card(x: int, label: str, value: str) -> list[str]:
    return [
        f"  <rect class=\"card border\" x=\"{x}\" y=\"78\" width=\"170\" height=\"58\" rx=\"8\" />",
        f"  <text class=\"muted\" x=\"{x + 16}\" y=\"102\" font-size=\"12\">{escape(label)}</text>",
        f"  <text class=\"text mono\" x=\"{x + 16}\" y=\"124\" font-size=\"17\" font-weight=\"600\">{escape(value)}</text>",
    ]


def section(title: str, items: list[dict], x: int, y: int, width: int) -> list[str]:
    lines = [
        f"  <text class=\"text\" x=\"{x}\" y=\"{y}\" font-size=\"14\" font-weight=\"600\">{escape(title)}</text>"
    ]

    if not items:
        lines.append(f"  <text class=\"muted\" x=\"{x}\" y=\"{y + 28}\" font-size=\"12\">No data yet</text>")
        return lines

    row_y = y + 30
    bar_width = width - 86
    for index, item in enumerate(items):
        current_y = row_y + index * 24
        percent = clamp_percent(item.get("percent", 0))
        fill_width = max(2, int(bar_width * percent / 100)) if percent > 0 else 0
        name = trim(str(item.get("name") or "Unknown"), 18)
        label = f"{percent:.0f}%"

        lines.extend(
            [
                f"  <text class=\"muted\" x=\"{x}\" y=\"{current_y}\" font-size=\"12\">{escape(name)}</text>",
                f"  <text class=\"muted\" x=\"{x + width}\" y=\"{current_y}\" font-size=\"12\" text-anchor=\"end\">{escape(label)}</text>",
                f"  <rect class=\"bar-bg\" x=\"{x}\" y=\"{current_y + 7}\" width=\"{bar_width}\" height=\"7\" rx=\"3.5\" />",
                f"  <rect class=\"bar\" x=\"{x}\" y=\"{current_y + 7}\" width=\"{fill_width}\" height=\"7\" rx=\"3.5\" />",
            ]
        )
    return lines


def normalized_items(items: object, limit: int) -> list[dict]:
    if not isinstance(items, list):
        return []

    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        percent = clamp_percent(item.get("percent", 0))
        if percent <= 0:
            continue
        normalized.append(
            {
                "name": str(item.get("name") or "Unknown"),
                "percent": percent,
                "text": str(item.get("text") or ""),
            }
        )
    return normalized[:limit]


def clamp_percent(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, number))


def format_seconds(value: object) -> str:
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return "No data"

    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours and minutes:
        return f"{hours} hrs {minutes} mins"
    if hours:
        return f"{hours} hrs"
    return f"{minutes} mins"


def human_range(stats_range: str) -> str:
    labels = {
        "last_7_days": "Last 7 days",
        "last_30_days": "Last 30 days",
        "last_6_months": "Last 6 months",
        "last_year": "Last year",
    }
    return labels.get(stats_range, stats_range.replace("_", " ").title())


def trim(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "..."


if __name__ == "__main__":
    sys.exit(main())
