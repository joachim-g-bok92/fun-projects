"""
data_prep.py
============
Preserves the original matchweek-assignment and full-league-position logic
(round-robin, 10 fixtures per matchweek) and adds per-game enrichment for
Arsenal: result, half-time drop, opponent, goals.

Public API
----------
get_arsenal_position_points(csv_path)              original API (unchanged)
get_arsenal_enriched(csv_path, extra_path=None)    full enriched table for dashboard
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════════
# ORIGINAL FUNCTIONS (unchanged)
# ═══════════════════════════════════════════════════════════════════════════════

def load_matches(csv_path: str | Path) -> pd.DataFrame:
    """Load the raw EPL matches CSV."""
    csv_path = Path(csv_path)
    df = pd.read_csv(csv_path)
    if not pd.api.types.is_datetime64_any_dtype(df["MatchDate"]):
        df["MatchDate"] = pd.to_datetime(df["MatchDate"])
    return df


def assign_matchweeks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assign matchweek 1-38 to each match so that each team plays exactly once
    per matchweek (proper round-robin). Used for correct end-of-matchweek
    league position.
    """
    df = df.copy()
    df = df.sort_values(["Season", "MatchDate", "HomeTeam", "AwayTeam"]).reset_index(drop=True)

    out_matchweeks: List[int] = []

    for season, season_df in df.groupby("Season", sort=False):
        teams_in_week: List[set] = [set() for _ in range(38)]
        weeks = []
        for _, row in season_df.iterrows():
            home = row["HomeTeam"]
            away = row["AwayTeam"]
            assigned = False
            for r in range(38):
                if home not in teams_in_week[r] and away not in teams_in_week[r]:
                    teams_in_week[r].add(home)
                    teams_in_week[r].add(away)
                    weeks.append(r + 1)
                    assigned = True
                    break
            if not assigned:
                weeks.append(38)
        out_matchweeks.extend(weeks)

    df["Matchweek"] = out_matchweeks
    return df


def _update_team_stats(
    stats: Dict[str, Dict[str, int]],
    team: str,
    goals_for: int,
    goals_against: int,
) -> None:
    s = stats[team]
    s["Played"] += 1
    s["GoalsFor"] += goals_for
    s["GoalsAgainst"] += goals_against
    if goals_for > goals_against:
        s["Won"] += 1
        s["Points"] += 3
    elif goals_for == goals_against:
        s["Drawn"] += 1
        s["Points"] += 1
    else:
        s["Lost"] += 1


def _empty_team_stats() -> Dict[str, int]:
    return {"Played": 0, "Won": 0, "Drawn": 0, "Lost": 0,
            "GoalsFor": 0, "GoalsAgainst": 0, "Points": 0}


def _build_table_and_ranks(team_stats: Dict[str, Dict[str, int]]) -> pd.DataFrame:
    rows: List[Dict] = []
    for team, s in team_stats.items():
        gd = s["GoalsFor"] - s["GoalsAgainst"]
        rows.append({"Team": team, "Points": s["Points"],
                     "GoalDifference": gd, "GoalsFor": s["GoalsFor"]})
    if not rows:
        return pd.DataFrame()
    table_df = pd.DataFrame(rows)
    table_df = table_df.sort_values(
        ["Points", "GoalDifference", "GoalsFor", "Team"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    table_df["Position"] = table_df.index + 1
    return table_df


def compute_arsenal_position_by_matchweek(csv_path: str | Path) -> pd.DataFrame:
    """
    Compute Arsenal's league position and points at the *end of each matchweek*
    (after all 10 fixtures in that round). Position at matchweek 38 = final
    league position.
    """
    df = load_matches(csv_path)
    df = assign_matchweeks(df)
    df = df.sort_values(
        ["Season", "Matchweek", "MatchDate", "HomeTeam", "AwayTeam"]
    ).reset_index(drop=True)

    records: List[Dict] = []

    for season, season_df in df.groupby("Season"):
        team_stats: Dict[str, Dict[str, int]] = defaultdict(_empty_team_stats)
        current_week = None

        def capture_arsenal(week: int) -> None:
            if "Arsenal" not in team_stats:
                return
            table = _build_table_and_ranks(team_stats)
            if table.empty:
                return
            arsenal_row = table.loc[table["Team"] == "Arsenal"].iloc[0]
            s = team_stats["Arsenal"]
            records.append({
                "Season": season,
                "Matchweek": week,
                "Team": "Arsenal",
                "Position": int(arsenal_row["Position"]),
                "Points": s["Points"],
                "GoalDifference": s["GoalsFor"] - s["GoalsAgainst"],
            })

        for _, row in season_df.iterrows():
            week = int(row["Matchweek"])
            if current_week is not None and week != current_week:
                capture_arsenal(current_week)
            current_week = week
            home = row["HomeTeam"]
            away = row["AwayTeam"]
            home_goals = int(row["FullTimeHomeGoals"])
            away_goals = int(row["FullTimeAwayGoals"])
            _update_team_stats(team_stats, home, home_goals, away_goals)
            _update_team_stats(team_stats, away, away_goals, home_goals)

        if current_week is not None:
            capture_arsenal(current_week)

    arsenal_df = pd.DataFrame.from_records(records)
    arsenal_df = arsenal_df.sort_values(["Season", "Matchweek"]).reset_index(drop=True)
    return arsenal_df


def load_arsenal_2025_26_points(base_dir: str | Path) -> pd.DataFrame | None:
    """
    Load Arsenal's 2025/26 PL results (Arsenal-only; no full league).
    Returns None if file not found.
    """
    path = Path(base_dir) / "arsenal_2025_26_pl.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["MatchDate"] = pd.to_datetime(df["MatchDate"])
    df = df.sort_values("MatchDate").reset_index(drop=True)
    records: List[Dict] = []
    points = 0
    gd = 0
    for i, row in df.iterrows():
        home = row["HomeTeam"]
        away = row["AwayTeam"]
        hg = int(row["FullTimeHomeGoals"])
        ag = int(row["FullTimeAwayGoals"])
        if home == "Arsenal":
            pts = 3 if hg > ag else (1 if hg == ag else 0)
            gd += hg - ag
        else:
            pts = 3 if ag > hg else (1 if ag == hg else 0)
            gd += ag - hg
        points += pts
        records.append({
            "Season": "2025/26",
            "Matchweek": len(records) + 1,
            "Team": "Arsenal",
            "Position": pd.NA,
            "Points": points,
            "GoalDifference": gd,
        })
    return pd.DataFrame.from_records(records)


def get_arsenal_position_points(csv_path: str | Path) -> pd.DataFrame:
    """
    Original public API (unchanged).
    Columns: Season, Matchweek, Team, Position, Points, GoalDifference.
    """
    main = compute_arsenal_position_by_matchweek(csv_path)
    base_dir = Path(csv_path).parent
    extra = load_arsenal_2025_26_points(base_dir)
    if extra is not None and len(extra) > 0:
        main = pd.concat([main, extra], ignore_index=True)
        main = main.sort_values(["Season", "Matchweek"]).reset_index(drop=True)
    return main


# ═══════════════════════════════════════════════════════════════════════════════
# ENRICHMENT LAYER  (new)
# ═══════════════════════════════════════════════════════════════════════════════

def _build_arsenal_per_game(df_with_mw: pd.DataFrame) -> pd.DataFrame:
    """
    Extract Arsenal rows from the full match DataFrame (which already has
    Matchweek assigned by assign_matchweeks) and compute per-game stats:
    Result, DroppedFromLead, Opponent, IsHome, GoalsFor, GoalsAgainst, MatchGD.

    DroppedFromLead = led at half-time but did not win the match.
    """
    ars = df_with_mw[
        (df_with_mw["HomeTeam"] == "Arsenal") | (df_with_mw["AwayTeam"] == "Arsenal")
    ].copy()

    records: List[Dict] = []
    for _, row in ars.iterrows():
        is_home = row["HomeTeam"] == "Arsenal"
        gf = int(row["FullTimeHomeGoals"] if is_home else row["FullTimeAwayGoals"])
        ga = int(row["FullTimeAwayGoals"] if is_home else row["FullTimeHomeGoals"])
        opp = row["AwayTeam"] if is_home else row["HomeTeam"]
        result = "W" if gf > ga else ("D" if gf == ga else "L")

        dropped = False
        if "HalfTimeHomeGoals" in row and pd.notna(row.get("HalfTimeHomeGoals")):
            hfg = int(row["HalfTimeHomeGoals"] if is_home else row["HalfTimeAwayGoals"])
            hga = int(row["HalfTimeAwayGoals"] if is_home else row["HalfTimeHomeGoals"])
            dropped = (hfg > hga) and (result != "W")

        records.append({
            "Season": row["Season"],
            "Matchweek": int(row["Matchweek"]),
            "Result": result,
            "DroppedFromLead": dropped,
            "Opponent": opp,
            "IsHome": is_home,
            "GoalsFor": gf,
            "GoalsAgainst": ga,
            "MatchGD": gf - ga,
        })

    return pd.DataFrame(records)


def _build_arsenal_per_game_2025_26(path: Path) -> pd.DataFrame | None:
    """Per-game enrichment for 2025/26 (no half-time data)."""
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["MatchDate"] = pd.to_datetime(df["MatchDate"])
    df = df.sort_values("MatchDate").reset_index(drop=True)
    records: List[Dict] = []
    for mw, (_, row) in enumerate(df.iterrows(), start=1):
        is_home = row["HomeTeam"] == "Arsenal"
        gf = int(row["FullTimeHomeGoals"] if is_home else row["FullTimeAwayGoals"])
        ga = int(row["FullTimeAwayGoals"] if is_home else row["FullTimeHomeGoals"])
        opp = row["AwayTeam"] if is_home else row["HomeTeam"]
        result = "W" if gf > ga else ("D" if gf == ga else "L")
        records.append({
            "Season": "2025/26",
            "Matchweek": mw,
            "Result": result,
            "DroppedFromLead": False,      # no HT data
            "Opponent": opp,
            "IsHome": is_home,
            "GoalsFor": gf,
            "GoalsAgainst": ga,
            "MatchGD": gf - ga,
        })
    return pd.DataFrame(records)


def get_arsenal_enriched(
    csv_path: str | Path,
    extra_path: str | Path | None = None,
) -> pd.DataFrame:
    """
    Full enriched table for the dashboard.

    Merges the original end-of-matchweek position/points table (full-league,
    round-robin matchweeks) with per-game detail.

    Columns:
        Season, Matchweek, Position, Points (cumulative), GoalDifference (cumulative),
        Result, DroppedFromLead, Opponent, IsHome, GoalsFor, GoalsAgainst, MatchGD
    """
    csv_path = Path(csv_path)

    # Base: Position + cumulative Points / GoalDifference (original logic)
    base = get_arsenal_position_points(csv_path)

    # Per-game enrichment for historical seasons
    df_full = load_matches(csv_path)
    df_full = assign_matchweeks(df_full)          # same MW logic as base
    per_game_hist = _build_arsenal_per_game(df_full)

    # Per-game enrichment for 2025/26
    extra_file = (
        Path(extra_path) if extra_path
        else csv_path.parent / "arsenal_2025_26_pl.csv"
    )
    per_game_2526 = _build_arsenal_per_game_2025_26(extra_file)

    per_game = (
        pd.concat([per_game_hist, per_game_2526], ignore_index=True)
        if per_game_2526 is not None
        else per_game_hist
    )

    # Merge on Season + Matchweek
    enriched = base.merge(per_game, on=["Season", "Matchweek"], how="left")
    enriched = enriched.drop(columns=["Team"], errors="ignore")
    enriched = enriched.sort_values(["Season", "Matchweek"]).reset_index(drop=True)

    return enriched


__all__ = [
    "load_matches",
    "assign_matchweeks",
    "compute_arsenal_position_by_matchweek",
    "load_arsenal_2025_26_points",
    "get_arsenal_position_points",
    "get_arsenal_enriched",
]
