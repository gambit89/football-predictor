"""Poisson model based only on goals for/against and venue splits."""

from math import exp, factorial

EPS = 0.08
RECENT_WEIGHT = 0.30
SEASON_WEIGHT = 0.70


def poisson_probability(goals, expected_goals):
    return exp(-expected_goals) * expected_goals ** goals / factorial(goals)


def score_matrix(lambda_home, lambda_away, max_goals=12):
    """Return a normalized independent-Poisson score probability matrix."""
    matrix = {
        f"{home}-{away}": poisson_probability(home, lambda_home)
        * poisson_probability(away, lambda_away)
        for home in range(max_goals + 1)
        for away in range(max_goals + 1)
    }
    total = sum(matrix.values())
    return {score: probability / total for score, probability in matrix.items()}


def _num(value):
    try:
        if value is None or value in ("-", ""):
            return None
        number = float(value)
        return number if number >= 0 else None
    except (TypeError, ValueError):
        return None


def _avg_from_stats(stats, side, kind):
    section = stats.get("goals", {}).get(kind, {}) if stats else {}
    return _num(section.get("average", {}).get(side))


def _recent_rates(fixtures, team_id, count=5):
    completed = []
    for item in fixtures or []:
        status = item.get("fixture", {}).get("status", {}).get("short")
        goals = item.get("goals", {})
        home_id = item.get("teams", {}).get("home", {}).get("id")
        away_id = item.get("teams", {}).get("away", {}).get("id")
        home_goals = _num(goals.get("home"))
        away_goals = _num(goals.get("away"))
        if status not in {"FT", "AET", "PEN"} or home_goals is None or away_goals is None:
            continue
        if home_id == team_id:
            completed.append((home_goals, away_goals))
        elif away_id == team_id:
            completed.append((away_goals, home_goals))
    completed = completed[-count:]
    if not completed:
        return None, None, 0
    return (
        sum(pair[0] for pair in completed) / len(completed),
        sum(pair[1] for pair in completed) / len(completed),
        len(completed),
    )


def _blend(season_value, recent_value):
    if season_value is None:
        return recent_value
    if recent_value is None:
        return season_value
    return SEASON_WEIGHT * season_value + RECENT_WEIGHT * recent_value


def build_team_profile(team_id, season_stats, last_fixtures):
    recent_for, recent_against, recent_n = _recent_rates(last_fixtures, team_id, 5)
    return {
        "team_id": team_id,
        "season_home_for": _avg_from_stats(season_stats, "home", "for"),
        "season_home_against": _avg_from_stats(season_stats, "home", "against"),
        "season_away_for": _avg_from_stats(season_stats, "away", "for"),
        "season_away_against": _avg_from_stats(season_stats, "away", "against"),
        "season_total_for": _avg_from_stats(season_stats, "total", "for"),
        "season_total_against": _avg_from_stats(season_stats, "total", "against"),
        "recent_for": recent_for,
        "recent_against": recent_against,
        "recent_matches": recent_n,
    }


def _summarize(lambda_home, lambda_away, home_profile=None, away_profile=None):
    matrix = score_matrix(lambda_home, lambda_away, 12)
    outcomes = {score: tuple(map(int, score.split("-"))) for score in matrix}
    total_goals = {score: sum(pair) for score, pair in outcomes.items()}
    home_win = sum(p for score, p in matrix.items() if outcomes[score][0] > outcomes[score][1])
    draw = sum(p for score, p in matrix.items() if outcomes[score][0] == outcomes[score][1])
    away_win = sum(p for score, p in matrix.items() if outcomes[score][0] < outcomes[score][1])
    markets = {}
    for threshold in (1.5, 2.5, 3.5):
        over = sum(p for score, p in matrix.items() if total_goals[score] > threshold)
        markets[f"over_{str(threshold).replace('.', '')}"] = over
        markets[f"under_{str(threshold).replace('.', '')}"] = 1 - over
    btts = sum(p for score, p in matrix.items() if all(goals > 0 for goals in outcomes[score]))
    return {
        "lambda_home": lambda_home,
        "lambda_away": lambda_away,
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        **markets,
        "btts": btts,
        "no_btts": 1 - btts,
        "most_likely_score": max(matrix.items(), key=lambda item: item[1])[0],
        "top_scores": sorted(matrix.items(), key=lambda item: item[1], reverse=True)[:10],
        "home_recent_matches": (home_profile or {}).get("recent_matches", 0),
        "away_recent_matches": (away_profile or {}).get("recent_matches", 0),
        "model_quality": "team_data" if home_profile and away_profile else "fallback",
    }


def predict_from_profiles(home_profile, away_profile, league_home_goals=1.45, league_away_goals=1.15):
    # Season venue splits are blended 70/30 with each team's last five matches.
    h_for = _blend(home_profile.get("season_home_for"), home_profile.get("recent_for"))
    h_against = _blend(home_profile.get("season_home_against"), home_profile.get("recent_against"))
    a_for = _blend(away_profile.get("season_away_for"), away_profile.get("recent_for"))
    a_against = _blend(away_profile.get("season_away_against"), away_profile.get("recent_against"))

    h_for = h_for if h_for is not None else home_profile.get("season_total_for")
    h_against = h_against if h_against is not None else home_profile.get("season_total_against")
    a_for = a_for if a_for is not None else away_profile.get("season_total_for")
    a_against = a_against if a_against is not None else away_profile.get("season_total_against")

    h_for = league_home_goals if h_for is None else h_for
    h_against = league_away_goals if h_against is None else h_against
    a_for = league_away_goals if a_for is None else a_for
    a_against = league_home_goals if a_against is None else a_against

    lambda_home = league_home_goals * (h_for / max(league_home_goals, EPS)) * (a_against / max(league_home_goals, EPS))
    lambda_away = league_away_goals * (a_for / max(league_away_goals, EPS)) * (h_against / max(league_away_goals, EPS))
    return _summarize(max(0.15, min(4.5, lambda_home)), max(0.15, min(4.5, lambda_away)), home_profile, away_profile)


def predict_match(home_strength=1.0, away_strength=1.0, league_goal_baseline=1.35):
    return _summarize(
        max(0.15, min(4.5, league_goal_baseline * float(home_strength))),
        max(0.15, min(4.5, league_goal_baseline * float(away_strength))),
    )

