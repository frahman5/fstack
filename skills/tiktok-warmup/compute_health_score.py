#!/usr/bin/env python3
"""
Compute a 0–100 health score for a TikTok warmup account.

Inputs (all optional — missing inputs lower the contribution from that
component without zeroing the score):
  --niche-pct     0.0–1.0   weighted FYP niche % over last 7 days (target: 0.70+)
  --follow-rate   float     follows / videos_watched over last 7 days (target: 0.04)
  --comment-rate  float     comments / session over last 7 days (target: 0.5+)
  --consistency   0.0–1.0   days_run / days_since_start_in_window (target: 0.85+)
  --error-rate    0.0–1.0   errored sessions / total sessions (target: <0.10)
  --json                    output as JSON instead of int

Component weights:
  niche_pct      40
  follow_rate    20
  comment_rate   15
  consistency    15
  error_rate     10
"""
import argparse, json, sys

WEIGHTS = {"niche": 40, "follow": 20, "comment": 15, "consistency": 15, "error": 10}

def clip01(x):
    if x is None:
        return None
    return max(0.0, min(1.0, x))

def score_niche(p):
    if p is None: return 0.5  # neutral when no data
    if p >= 0.70: return 1.0
    if p >= 0.50: return 0.6 + (p - 0.50) * 2.0
    return p / 0.50 * 0.6  # 0..0.5 maps to 0..0.6

def score_follow(rate):
    if rate is None: return 0.5
    target = 0.04
    return min(1.0, rate / target)

def score_comment(rate):
    if rate is None: return 0.5
    target = 0.5
    return min(1.0, rate / target)

def score_consistency(c):
    if c is None: return 0.5
    if c >= 0.85: return 1.0
    return c / 0.85

def score_error(e):
    if e is None: return 1.0
    if e <= 0.10: return 1.0
    if e >= 0.50: return 0.0
    return 1.0 - (e - 0.10) / 0.40

def compute(niche_pct, follow_rate, comment_rate, consistency, error_rate):
    components = {
        "niche":       score_niche(clip01(niche_pct)),
        "follow":      score_follow(follow_rate),
        "comment":     score_comment(comment_rate),
        "consistency": score_consistency(clip01(consistency)),
        "error":       score_error(clip01(error_rate)),
    }
    score = sum(WEIGHTS[k] * v for k, v in components.items())
    return round(score), components

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--niche-pct", type=float, default=None)
    p.add_argument("--follow-rate", type=float, default=None)
    p.add_argument("--comment-rate", type=float, default=None)
    p.add_argument("--consistency", type=float, default=None)
    p.add_argument("--error-rate", type=float, default=None)
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    score, components = compute(a.niche_pct, a.follow_rate, a.comment_rate, a.consistency, a.error_rate)
    if a.json:
        print(json.dumps({"score": score, "components": components, "weights": WEIGHTS}))
    else:
        print(score)

if __name__ == "__main__":
    main()
