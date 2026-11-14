
from math import exp, factorial

EPS = 0.08


def poisson_probability(goals, expected_goals):
    return (
        exp(-expected_goals)
        * expected_goals ** goals
        / factorial(goals)
    )


def score_matrix(lambda_home, lambda_away, max_goals=8):
    return {
        f"{h}-{a}": (
            poisson_probability(h, lambda_home)
            * poisson_probability(a, lambda_away)
        )
        for h in range(max_goals + 1)
        for a in range(max_goals + 1)
    }


def _num(value):
    try:
        if value is None or value in ("-", ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _avg_from_stats(stats, side, kind):
    section = stats.get("goals", {}).get(kind, {}) if stats else {}
    return _num(section.get("average", {}).get(side))


def _recent_rates(fixtures, team_id):
    completed = []

    for item in fixtures or []:
        status = item.get("fixture", {}).get("status", {}).get("short")
        goals = item.get("goals", {})
        home = item.get("teams", {}).get("home", {}).get("id")
        away = item.get("teams", {}).get("away", {}).get("id")

        gh = _num(goals.get("home"))
        ga = _num(goals.get("away"))

        if status not in {"FT", "AET", "PEN"}:
            continue

        if gh is None or ga is None:
            continue

        if home == team_id:
            completed.append((gh, ga))
        elif away == team_id:
            completed.append((ga, gh))

    completed = completed[-10:]

    if not completed:
        return None, None, 0

    weights = list(range(1, len(completed) + 1))
    total = sum(weights)

    gf = sum(
        pair[0] * weight
        for pair, weight in zip(completed, weights)
    ) / total

    ga = sum(
        pair[1] * weight
        for pair, weight in zip(completed, weights)
    ) / total

    return gf, ga, len(completed)


def _blend(season_value, recent_value, recent_weight=0.35):
    if season_value is None and recent_value is None:
        return None

    if season_value is None:
        return recent_value

    if recent_value is None:
        return season_value

    return (
        (1 - recent_weight) * season_value
        + recent_weight * recent_value
    )


def build_team_profile(team_id, season_stats, last_fixtures):
    recent_for, recent_against, recent_n = _recent_rates(
        last_fixtures, team_id
    )

    return {
        "team_id": team_id,
        "season_home_for": _avg_from_stats(
            season_stats, "home", "for"
        ),
        "season_home_against": _avg_from_stats(
            season_stats, "home", "against"
        ),
        "season_away_for": _avg_from_stats(
            season_stats, "away", "for"
        ),
        "season_away_against": _avg_from_stats(
            season_stats, "away", "against"
        ),
        "season_total_for": _avg_from_stats(
            season_stats, "total", "for"
        ),
        "season_total_against": _avg_from_stats(
            season_stats, "total", "against"
        ),
        "recent_for": recent_for,
        "recent_against": recent_against,
        "recent_matches": recent_n,
    }


def predict_from_profiles(
    home_profile,
    away_profile,
    league_home_goals=1.45,
    league_away_goals=1.15
):
    h_for = _blend(
        home_profile.get("season_home_for"),
        home_profile.get("recent_for")
    )

    h_against = _blend(
        home_profile.get("season_home_against"),
        home_profile.get("recent_against")
    )

    a_for = _blend(
        away_profile.get("season_away_for"),
        away_profile.get("recent_for")
    )

    a_against = _blend(
        away_profile.get("season_away_against"),
        away_profile.get("recent_against")
    )

    h_for = (
        h_for
        or home_profile.get("season_total_for")
        or league_home_goals
    )

    h_against = (
        h_against
        or home_profile.get("season_total_against")
        or league_away_goals
    )

    a_for = (
        a_for
        or away_profile.get("season_total_for")
        or league_away_goals
    )

    a_against = (
        a_against
        or away_profile.get("season_total_against")
        or league_home_goals
    )

    lh = (
        league_home_goals
        * (h_for / max(league_home_goals, EPS))
        * (a_against / max(league_home_goals, EPS))
    )

    la = (
        league_away_goals
        * (a_for / max(league_away_goals, EPS))
        * (h_against / max(league_away_goals, EPS))
    )

    lh = max(0.15, min(4.5, lh))
    la = max(0.15, min(4.5, la))

    return _summarize(lh, la, home_profile, away_profile)


def _summarize(lh, la, home_profile=None, away_profile=None):
    matrix = score_matrix(lh, la, 10)

    home_win = sum(
        p for score, p in matrix.items()
        if int(score.split("-")[0]) > int(score.split("-")[1])
    )

    draw = sum(
        p for score, p in matrix.items()
        if int(score.split("-")[0]) == int(score.split("-")[1])
    )

    away_win = sum(
        p for score, p in matrix.items()
        if int(score.split("-")[0]) < int(score.split("-")[1])
    )

    over25 = sum(
        p for score, p in matrix.items()
        if sum(map(int, score.split("-"))) >= 3
    )

    btts = sum(
        p for score, p in matrix.items()
        if all(int(x) > 0 for x in score.split("-"))
    )

    likely = max(matrix.items(), key=lambda x: x[1])[0]

    return {
        "lambda_home": lh,
        "lambda_away": la,
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        "over_25": over25,
        "under_25": 1 - over25,
        "btts": btts,
        "most_likely_score": likely,
        "home_recent_matches": (
            home_profile or {}
        ).get("recent_matches", 0),
        "away_recent_matches": (
            away_profile or {}
        ).get("recent_matches", 0),
        "model_quality": (
            "team_data"
            if home_profile and away_profile
            else "fallback"
        )
    }


def predict_match(
    home_strength=1.0,
    away_strength=1.0,
    league_goal_baseline=1.35
):
    lh = max(
        0.15,
        min(4.5, league_goal_baseline * float(home_strength))
    )

    la = max(
        0.15,
        min(4.5, league_goal_baseline * float(away_strength))
    )

    return _summarize(lh, la)
