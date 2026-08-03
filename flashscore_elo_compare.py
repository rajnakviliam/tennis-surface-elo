import csv
from collections import Counter
from pathlib import Path


ATP_ELO_FILE = Path("atp_elo.csv")
WTA_ELO_FILE = Path("wta_elo.csv")

ATP_RANKINGS_FILE = Path("atp_rankings.csv")
WTA_RANKINGS_FILE = Path("wta_rankings.csv")

ALIASES_FILE = Path("aliases.csv")
MATCHES_FILE = Path("flashscore_matches.csv")

OUTPUT_FILE = Path("flashscore_elo_matches.csv")
MISMATCH_FILE = Path("ranking_vs_elo_mismatch.csv")
SKIPPED_FILE = Path("skipped_matches.csv")


SURFACE_RANK_COLUMN = {
    "hard": "HardEloRank",
    "clay": "ClayEloRank",
    "grass": "GrassEloRank",
}

SURFACE_ELO_COLUMN = {
    "hard": "HardElo",
    "clay": "ClayElo",
    "grass": "GrassElo",
}


def load_player_database(path: Path) -> dict:
    players = {}

    if not path.exists():
        raise FileNotFoundError(f"Súbor neexistuje: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")

        for row in reader:
            player = (row.get("Player") or "").strip()

            if player:
                players[player] = row

    return players


def load_aliases(path: Path) -> dict:
    aliases = {}

    if not path.exists():
        raise FileNotFoundError(f"Súbor neexistuje: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")

        for row in reader:
            alias = (row.get("TE_Name") or "").strip()
            canonical = (row.get("TA_Name") or "").strip()
            tour = (row.get("Tour") or "").strip().upper()

            if alias and canonical and tour in {"ATP", "WTA"}:
                aliases[alias] = {
                    "TA_Name": canonical,
                    "Tour": tour,
                }

    return aliases


def optional_int(value):
    value = (value or "").strip()

    if not value:
        return ""

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return ""


def optional_float(value):
    value = (value or "").strip()

    if not value:
        return ""

    try:
        return float(value)
    except (TypeError, ValueError):
        return ""


def add_skipped(skipped, stats, row, reason, detail=""):
    stats[reason] += 1

    skipped.append({
        "DateLabel": row.get("DateLabel", ""),
        "Tour": row.get("Tour", ""),
        "Tournament": row.get("Tournament", ""),
        "Surface": row.get("Surface", ""),
        "Time": row.get("Time", ""),
        "Player 1": row.get("Player 1", ""),
        "Player 2": row.get("Player 2", ""),
        "Reason": reason,
        "Detail": detail,
    })


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            delimiter=";",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def read_elo_values(player_name: str, elo_db: dict, surface: str) -> dict:
    if player_name not in elo_db:
        return {
            "has_elo": False,
            "overall_elo_rank": "",
            "surface_elo_rank": "",
            "overall_elo": "",
            "surface_elo": "",
        }

    row = elo_db[player_name]

    overall_elo_rank = optional_int(row.get("EloRank"))
    surface_elo_rank = optional_int(
        row.get(SURFACE_RANK_COLUMN[surface])
    )
    overall_elo = optional_float(row.get("Elo"))
    surface_elo = optional_float(
        row.get(SURFACE_ELO_COLUMN[surface])
    )

    has_elo = all(
        value != ""
        for value in (
            overall_elo_rank,
            surface_elo_rank,
            overall_elo,
            surface_elo,
        )
    )

    return {
        "has_elo": has_elo,
        "overall_elo_rank": overall_elo_rank if has_elo else "",
        "surface_elo_rank": surface_elo_rank if has_elo else "",
        "overall_elo": overall_elo if has_elo else "",
        "surface_elo": surface_elo if has_elo else "",
    }


def main():
    atp_elo = load_player_database(ATP_ELO_FILE)
    wta_elo = load_player_database(WTA_ELO_FILE)

    atp_rankings = load_player_database(ATP_RANKINGS_FILE)
    wta_rankings = load_player_database(WTA_RANKINGS_FILE)

    aliases = load_aliases(ALIASES_FILE)

    rows_out = []
    skipped = []
    stats = Counter()

    if not MATCHES_FILE.exists():
        raise FileNotFoundError(f"Súbor neexistuje: {MATCHES_FILE}")

    with MATCHES_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file, delimiter=";")

        for row in reader:
            stats["loaded_matches"] += 1

            p1_alias = (row.get("Player 1") or "").strip()
            p2_alias = (row.get("Player 2") or "").strip()

            if not p1_alias:
                add_skipped(
                    skipped,
                    stats,
                    row,
                    "missing_player_1_name",
                )
                continue

            if not p2_alias:
                add_skipped(
                    skipped,
                    stats,
                    row,
                    "missing_player_2_name",
                )
                continue

            if p1_alias not in aliases:
                add_skipped(
                    skipped,
                    stats,
                    row,
                    "player_1_not_in_aliases",
                    p1_alias,
                )
                continue

            if p2_alias not in aliases:
                add_skipped(
                    skipped,
                    stats,
                    row,
                    "player_2_not_in_aliases",
                    p2_alias,
                )
                continue

            p1 = aliases[p1_alias]["TA_Name"]
            p2 = aliases[p2_alias]["TA_Name"]

            tour1 = aliases[p1_alias]["Tour"]
            tour2 = aliases[p2_alias]["Tour"]

            if tour1 != tour2:
                add_skipped(
                    skipped,
                    stats,
                    row,
                    "tour_mismatch",
                    f"{p1_alias}={tour1}; {p2_alias}={tour2}",
                )
                continue

            if tour1 not in {"ATP", "WTA"}:
                add_skipped(
                    skipped,
                    stats,
                    row,
                    "unknown_tour",
                    tour1,
                )
                continue

            ranking_db = atp_rankings if tour1 == "ATP" else wta_rankings
            elo_db = atp_elo if tour1 == "ATP" else wta_elo

            if p1 not in ranking_db:
                add_skipped(
                    skipped,
                    stats,
                    row,
                    "player_1_not_in_rankings",
                    p1,
                )
                continue

            if p2 not in ranking_db:
                add_skipped(
                    skipped,
                    stats,
                    row,
                    "player_2_not_in_rankings",
                    p2,
                )
                continue

            rank1 = optional_int(ranking_db[p1].get("Rank"))
            rank2 = optional_int(ranking_db[p2].get("Rank"))

            if rank1 == "":
                add_skipped(
                    skipped,
                    stats,
                    row,
                    "missing_or_invalid_rank",
                    f"{p1}: {ranking_db[p1].get('Rank', '')}",
                )
                continue

            if rank2 == "":
                add_skipped(
                    skipped,
                    stats,
                    row,
                    "missing_or_invalid_rank",
                    f"{p2}: {ranking_db[p2].get('Rank', '')}",
                )
                continue

            surface = (row.get("Surface") or "").strip().lower()

            if surface not in SURFACE_RANK_COLUMN:
                add_skipped(
                    skipped,
                    stats,
                    row,
                    "unknown_surface",
                    surface,
                )
                continue

            p1_elo = read_elo_values(p1, elo_db, surface)
            p2_elo = read_elo_values(p2, elo_db, surface)

            if not p1_elo["has_elo"]:
                stats["player_1_without_elo"] += 1

            if not p2_elo["has_elo"]:
                stats["player_2_without_elo"] += 1

            both_have_elo = (
                p1_elo["has_elo"]
                and p2_elo["has_elo"]
            )

            if both_have_elo:
                stats["matches_with_full_elo"] += 1
            else:
                stats["matches_without_full_elo"] += 1

            if rank1 < rank2:
                ranking_favorite = p1
            elif rank2 < rank1:
                ranking_favorite = p2
            else:
                ranking_favorite = ""

            if both_have_elo:
                overall_elo1 = p1_elo["overall_elo"]
                overall_elo2 = p2_elo["overall_elo"]
                surface_elo1 = p1_elo["surface_elo"]
                surface_elo2 = p2_elo["surface_elo"]

                if surface_elo1 > surface_elo2:
                    elo_favorite = p1
                elif surface_elo2 > surface_elo1:
                    elo_favorite = p2
                else:
                    elo_favorite = ""

                overall_elo_diff = round(
                    abs(overall_elo1 - overall_elo2),
                    1,
                )
                surface_elo_diff = round(
                    abs(surface_elo1 - surface_elo2),
                    1,
                )
            else:
                elo_favorite = ""
                overall_elo_diff = ""
                surface_elo_diff = ""

            rows_out.append({
                "DateLabel": row.get("DateLabel", ""),
                "Tour": tour1,
                "Tournament": row.get("Tournament", ""),
                "Surface": surface,
                "Time": row.get("Time", ""),
                "Player 1": p1,
                "Player 2": p2,
                "Rank 1": rank1,
                "Rank 2": rank2,
                "Rank Diff": abs(rank1 - rank2),
                "Overall Elo Rank 1": p1_elo["overall_elo_rank"],
                "Overall Elo Rank 2": p2_elo["overall_elo_rank"],
                "Surface Elo Rank 1": p1_elo["surface_elo_rank"],
                "Surface Elo Rank 2": p2_elo["surface_elo_rank"],
                "Overall Elo 1": (
                    round(p1_elo["overall_elo"], 1)
                    if p1_elo["has_elo"]
                    else ""
                ),
                "Overall Elo 2": (
                    round(p2_elo["overall_elo"], 1)
                    if p2_elo["has_elo"]
                    else ""
                ),
                "Surface Elo 1": (
                    round(p1_elo["surface_elo"], 1)
                    if p1_elo["has_elo"]
                    else ""
                ),
                "Surface Elo 2": (
                    round(p2_elo["surface_elo"], 1)
                    if p2_elo["has_elo"]
                    else ""
                ),
                "Overall Elo Diff": overall_elo_diff,
                "Surface Elo Diff": surface_elo_diff,
                "Ranking Favorite": ranking_favorite,
                "ELO Favorite": elo_favorite,
                "Has Elo 1": p1_elo["has_elo"],
                "Has Elo 2": p2_elo["has_elo"],
                "Both Have Elo": both_have_elo,
            })

            stats["included_matches"] += 1

    rows_out.sort(
        key=lambda row: (
            row["DateLabel"],
            row["Time"],
            row["Tournament"],
        )
    )

    output_fieldnames = [
        "DateLabel",
        "Tour",
        "Tournament",
        "Surface",
        "Time",
        "Player 1",
        "Player 2",
        "Rank 1",
        "Rank 2",
        "Rank Diff",
        "Overall Elo Rank 1",
        "Overall Elo Rank 2",
        "Surface Elo Rank 1",
        "Surface Elo Rank 2",
        "Overall Elo 1",
        "Overall Elo 2",
        "Surface Elo 1",
        "Surface Elo 2",
        "Overall Elo Diff",
        "Surface Elo Diff",
        "Ranking Favorite",
        "ELO Favorite",
        "Has Elo 1",
        "Has Elo 2",
        "Both Have Elo",
    ]

    write_csv(
        OUTPUT_FILE,
        rows_out,
        output_fieldnames,
    )

    mismatches = [
        row
        for row in rows_out
        if (
            row["Both Have Elo"]
            and row["Ranking Favorite"]
            and row["ELO Favorite"]
            and row["Ranking Favorite"] != row["ELO Favorite"]
        )
    ]

    mismatches.sort(
        key=lambda row: (
            row["Surface Elo Diff"]
            if row["Surface Elo Diff"] != ""
            else -1
        ),
        reverse=True,
    )

    write_csv(
        MISMATCH_FILE,
        mismatches,
        output_fieldnames,
    )

    skipped_fieldnames = [
        "DateLabel",
        "Tour",
        "Tournament",
        "Surface",
        "Time",
        "Player 1",
        "Player 2",
        "Reason",
        "Detail",
    ]

    write_csv(
        SKIPPED_FILE,
        skipped,
        skipped_fieldnames,
    )

    print()
    print("=" * 56)
    print("FLASHSCORE -> RANKING + ELO DIAGNOSTIKA")
    print("=" * 56)
    print(
        f"Načítaných zápasov:              "
        f"{stats['loaded_matches']}"
    )
    print(
        f"Výsledných zápasov:              "
        f"{stats['included_matches']}"
    )
    print(
        f"Vyradených zápasov:              "
        f"{len(skipped)}"
    )
    print(
        f"Zápasov s kompletným Elo:        "
        f"{stats['matches_with_full_elo']}"
    )
    print(
        f"Zápasov bez kompletného Elo:     "
        f"{stats['matches_without_full_elo']}"
    )
    print(
        f"Hráč 1 bez Elo:                  "
        f"{stats['player_1_without_elo']}"
    )
    print(
        f"Hráč 2 bez Elo:                  "
        f"{stats['player_2_without_elo']}"
    )

    print()
    print("Dôvody vyradenia:")

    reason_keys = [
        "missing_player_1_name",
        "missing_player_2_name",
        "player_1_not_in_aliases",
        "player_2_not_in_aliases",
        "tour_mismatch",
        "unknown_tour",
        "player_1_not_in_rankings",
        "player_2_not_in_rankings",
        "missing_or_invalid_rank",
        "unknown_surface",
    ]

    printed = False

    for reason in reason_keys:
        count = stats[reason]

        if count:
            printed = True
            print(f"  {reason}: {count}")

    if not printed:
        print("  žiadne")

    print()
    print(
        f"Ranking vs ELO mismatch:         "
        f"{len(mismatches)}"
    )
    print(f"Výstup:                          {OUTPUT_FILE}")
    print(f"Mismatch výstup:                 {MISMATCH_FILE}")
    print(
        f"Diagnostika vyradených zápasov:  "
        f"{SKIPPED_FILE}"
    )
    print("=" * 56)


if __name__ == "__main__":
    main()
