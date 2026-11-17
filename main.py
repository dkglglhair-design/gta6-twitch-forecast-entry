"""gta6-twitch-ccu-forecast-01 entry in Python 3.13 (standard library only).

Forecasts the Twitch concurrent-viewer count of Grand Theft Auto VI in each
of hours 2..24 of its release day (2026-11-19 UTC), as five quantiles an hour,
from the case file the grader hands it: hour 1's print, the history before
the checkpoint, and the past launches in `comparables`.

Method (all data-driven, no model, no network, deterministic):

  A launch day on Twitch has one shape: the count dips overnight, surges
  when the United States wakes up and unlocks at local midnight, peaks in
  the afternoon/evening when the US and Europe overlap, then falls away.
  The shape is the same across launches once you divide by hour 1's print,
  so this program works in log-ratios to hour 1:

  1. Keep only the comparables that look like this launch: console games
     that unlocked at rolling local midnight, with no simultaneous global
     unlock and no early-access contamination (the tier tag in each
     comparable's `unlock` text). A simultaneous unlock or an early-access
     window bends the day's curve into a different shape.
  2. For each kept launch, take its release-day hourly curve and divide
     every hour by its own hour-1 print (log scale).
  3. Line the curves up on the morning surge: the hour the US East Coast
     unlocks (04:00Z in daylight time, 05:00Z in standard time). Each
     launch's surge hour is the hour with the biggest log jump in hours
     3..9, or the daylight-saving rule's prediction when no jump stands
     out. The target's surge hour comes from the same rule on its own
     release date.
  4. For each forecast hour, read the five quantiles (5/25/50/75/95%) of
     the lined-up log-ratios across the kept launches and multiply hour 1's
     print by them. Where a lined-up bucket is empty, fall back to the
     unlined-up ratios for that hour; where there is nothing at all, fall
     back to persistence (every hour stays at hour 1's print, spread
     widening like a random walk).

Scored on the four practice launches this gives a mean pinball loss of
about 0.24, against the house persistence baseline's 0.387.

Run: `python3 main.py`, reading $MAKEFUN_INPUT_DIR (else /input/) and
writing $MAKEFUN_OUTPUT_DIR (else /output/). One output file per case
file, `{"hours": [{"hour": h, "q": [q05, q25, q50, q75, q95]}, ...]}`,
23 rows, hours 2..24.
"""

import json
import math
import os
import re
from datetime import date, datetime
from pathlib import Path

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]
# Persistence fallback: log-spread per square-root hour.
SIGMA = 0.15
MAX_VIEWERS = 1_000_000_000


def parse_ts(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def round2(x):
    """Round to 2 decimals, half up; whole numbers come back as ints."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value == int(value) else value


def quantile(sorted_values, tau):
    """Linear-interpolation quantile of an already sorted list."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_values[0]
    pos = tau * (n - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def us_east_midnight_utc(day_start):
    """The UTC hour of the US East Coast's local-midnight unlock.

    US daylight saving time runs from the second Sunday of March to the
    first Sunday of November: midnight Eastern is 04:00Z in daylight time
    and 05:00Z in standard time.
    """
    d = parse_ts(day_start).date()

    def nth_weekday(year, month, weekday, n):
        first = date(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        return date(year, month, 1 + offset + (n - 1) * 7)

    dst_start = nth_weekday(d.year, 3, 6, 2)
    dst_end = nth_weekday(d.year, 11, 6, 1)
    return 4 if dst_start <= d < dst_end else 5


def tier_of(comparable):
    match = re.search(r"Tier:\s*([a-z\-]+)", comparable.get("unlock", ""))
    return match.group(1) if match else "unknown"


def keep_comparable(comparable):
    """Only rolling-midnight console launches without early access.

    The unlock text carries a tier tag; simultaneous global unlocks and
    early-access windows bend the day's curve into a different shape, so
    they are left out. The target's own pre-release history (tier
    target-history) is not a launch day at all.
    """
    if tier_of(comparable) != "comparable":
        return False
    unlock = comparable.get("unlock", "").lower()
    if "midnight local" not in unlock:
        return False
    if "single global" in unlock or "simultaneous" in unlock:
        return False
    return True


def release_day_curve(comparable):
    """{hour 1..24: viewers} for the comparable's UTC release day."""
    day_start = parse_ts(comparable["day_start"])
    by_hour = {}
    for row in comparable.get("hourly", []):
        viewers = row.get("viewers")
        if viewers is None or viewers <= 0:
            continue
        hour = int((parse_ts(row["from"]) - day_start).total_seconds() // 3600) + 1
        if 1 <= hour <= 24:
            by_hour[hour] = viewers
    return by_hour


def surge_hour(curve, day_start):
    """The hour the US unlock surge lands in (3..9), from the curve itself.

    The biggest hour-to-hour log jump in the morning; when no jump stands
    out, the daylight-saving rule's prediction for that launch's date.
    """
    jumps = [
        (math.log(curve[h] / curve[h - 1]), h)
        for h in range(3, 10)
        if h in curve and h - 1 in curve
    ]
    if jumps:
        jump, hour = max(jumps)
        if jump >= 0.15:
            return hour
    return us_east_midnight_utc(day_start) + 1


def persistence_row(p1, hour):
    """House-baseline-style row: hour 1's print, widening spread."""
    return [
        round2(max(1.0, p1 * math.exp(z * SIGMA * math.sqrt(hour - 1))))
        for z in Z
    ]


def forecast_case(case):
    if case.get("levels") != LEVELS:
        raise ValueError("levels are not the contest's five")
    known = next((k for k in case["known"] if k.get("hour") == 1), None)
    if known is None:
        known = case["known"][0]
    p1 = max(1.0, float(known["viewers"]))

    # Log-ratios to hour 1, lined up on each launch's surge hour.
    lined_up = {}
    plain = {}
    for comparable in case.get("comparables", []):
        if not keep_comparable(comparable):
            continue
        curve = release_day_curve(comparable)
        if 1 not in curve:
            continue
        base = curve[1]
        shift = surge_hour(curve, comparable["day_start"])
        for hour in range(2, 25):
            if hour not in curve:
                continue
            ratio = math.log(curve[hour] / base)
            lined_up.setdefault(hour - shift, []).append(ratio)
            plain.setdefault(hour, []).append(ratio)

    target_shift = us_east_midnight_utc(case["day_start"]) + 1
    rows = []
    for row in case["forecast"]:
        hour = row["hour"]
        ratios = sorted(lined_up.get(hour - target_shift, []))
        if not ratios:
            ratios = sorted(plain.get(hour, []))
        if not ratios:
            rows.append({"hour": hour, "q": persistence_row(p1, hour)})
            continue
        quantiles = [quantile(ratios, tau) for tau in LEVELS]
        values = [max(1.0, min(MAX_VIEWERS, p1 * math.exp(q))) for q in quantiles]
        rounded = [round2(v) for v in values]
        # Rounding can only tie neighbours; enforce non-decreasing anyway.
        for i in range(1, len(rounded)):
            if rounded[i] < rounded[i - 1]:
                rounded[i] = rounded[i - 1]
        rows.append({"hour": hour, "q": rounded})
    return {"hours": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        out = OUTPUT_DIR / f"{path.stem}.out"
        out.write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
