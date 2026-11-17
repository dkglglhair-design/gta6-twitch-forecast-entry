[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/dkglglhair-design/gta6-twitch-forecast-entry/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/dkglglhair-design/gta6-twitch-forecast-entry/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

# GTA VI launch-day Twitch forecast

Entry for [gta6-twitch-ccu-forecast-01](https://make.fun/c/gta6-twitch-ccu-forecast-01)
on make.fun: forecast the Twitch concurrent viewers of Grand Theft Auto VI
in each of hours 2–24 of its release day (2026-11-19 UTC), as five quantiles
(0.05 / 0.25 / 0.5 / 0.75 / 0.95) per hour.

## Method

`main.py` (Python 3.13, standard library only, no network, deterministic)
works in log-ratios to hour 1's print, because a launch day on Twitch has
one shape once you divide by hour 1: a dip overnight, a surge when the US
East Coast wakes up and unlocks at local midnight, a peak in the
afternoon/evening, then a fall away.

1. **Keep only look-alike launches.** From the case's `comparables`, keep
   console games that unlocked at rolling local midnight with no
   simultaneous global unlock and no early-access contamination (the tier
   tag in each comparable's `unlock` text). Simultaneous unlocks and
   early-access windows bend the day's curve into a different shape.
2. **Normalise.** Each kept launch's release-day hourly curve is divided
   by its own hour-1 print (log scale).
3. **Line up on the morning surge.** The surge hour is the hour with the
   biggest log jump in hours 3–9, or the daylight-saving rule's prediction
   (US East midnight is 04:00Z in daylight time, 05:00Z in standard time)
   when no jump stands out. The target's surge hour comes from the same
   rule on its own release date (2026-11-19 is standard time, so the surge
   lands in hour 6).
4. **Read the quantiles.** For each forecast hour, the five quantiles of
   the lined-up log-ratios across the kept launches, multiplied by hour 1's
   print. Empty buckets fall back to the unlined-up ratios for that hour,
   and then to persistence (hour 1's print, spread widening like a random
   walk).

## Practice results

Scored against the real SullyGnome answers for the four practice launches
(Marvel's Wolverine, Red Dead Redemption 2, God of War Ragnarök, Marvel's
Spider-Man 2), mean pinball loss on the log scale:

| | p00 | p01 | p02 | p03 | mean |
|---|---|---|---|---|---|
| this entry | 0.3950 | 0.1170 | 0.2158 | 0.2385 | **0.2416** |
| house persistence baseline | 0.7437 | 0.2868 | 0.2146 | 0.3033 | 0.3871 |

Two ideas were tested and rejected: hour-1 viewers-per-channel as a
predictor of the peak ratio (correlation −0.18 across all 37 comparables —
the pattern in the four practice cases was a coincidence), and trend
extrapolation (overfits the five sample cases).

## Run

```sh
python3 main.py   # reads $MAKEFUN_INPUT_DIR (else /input/), writes $MAKEFUN_OUTPUT_DIR (else /output/)
```
