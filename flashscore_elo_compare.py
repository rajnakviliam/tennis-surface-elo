import csv
from collections import Counter
from pathlib import Path

ATP_ELO_FILE = Path("atp_elo.csv")
WTA_ELO_FILE = Path("wta_elo.csv")
NAME_MAP_FILE = Path("name_map.csv")
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
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            name = (row.get("Player") or "").strip()
            if name:
                players[name] = row
    return players


def load_name_map(path: Path) -> dict:
    mapping = {}
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            te_name = (row.get("TE_Name") or "").strip()
            if te_name:
                mapping[te_name] = {
                    "TA_Name": (row.get("TA_Name") or "").strip(),
                    "Tour": (row.get("Tour") or "").strip().upper(),
                }
    return mapping


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


def require_int(value, field_name):
    value = (value or "").strip()
    if not value:
        raise ValueError(f"missing_{field_name}")
    return int(float(value))


def require_float(value, field_name):
    value = (value or "").strip()
    if not value:
        raise ValueError(f"missing_{field_name}")
    return float(value)


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter=";",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    atp = load_player_database(ATP_ELO_FILE)
    wta = load_player_database(WTA_ELO_FILE)
    name_map = load_name_map(NAME_MAP_FILE)

    rows_out = []
    skipped = []
    stats = Counter()

    with MATCHES_FILE.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")

        for row in reader:
            stats["loaded_matches"] += 1

            p1_te = (row.get("Player 1") or "").strip()
            p2_te = (row.get("Player 2") or "").strip()

            if not p1_te:
                add_skipped(skipped, stats, row, "missing_player_1_name")
                continue

            if not p2_te:
                add_skipped(skipped, stats, row, "missing_player_2_name")
                continue

            if p1_te not in name_map:
                add_skipped(skipped, stats, row, "player_1_not_in_name_map", p1_te)
                continue

            if p2_te not in name_map:
                add_skipped(skipped, stats, row, "player_2_not_in_name_map", p2_te)
                continue

            p1 = name_map[p1_te]["TA_Name"]
            p2 = name_map[p2_te]["TA_Name"]
            tour1 = name_map[p1_te]["Tour"]
            tour2 = name_map[p2_te]["Tour"]

            if tour1 != tour2:
                add_skipped(
                    skipped,
                    stats,
                    row,
                    "tour_mismatch",
                    f"{p1_te}={tour1}; {p2_te}={tour2}",
                )
                continue

            if tour1 not in {"ATP", "WTA"}:
                add_skipped(skipped, stats, row, "unknown_tour", tour1)
                continue

            db = atp if tour1 == "ATP" else wta

            if p1 not in db:
                add_skipped(skipped, stats, row, "player_1_not_in_elo_database", p1)
                continue

            if p2 not in db:
                add_skipped(skipped, stats, row, "player_2_not_in_elo_database", p2)
                continue

            surface = (row.get("Surface") or "").strip().lower()

            if surface not in SURFACE_RANK_COLUMN:
                add_skipped(skipped, stats, row, "unknown_surface", surface)
                continue

            rank_col = SURFACE_RANK_COLUMN[surface]
            surface_elo_col = SURFACE_ELO_COLUMN[surface]

            try:
                rank1 = require_int(db[p1].get("Rank"), "rank_1")
                rank2 = require_int(db[p2].get("Rank"), "rank_2")

                overall_elo_rank1 = require_int(db[p1].get("EloRank"), "overall_elo_rank_1")
                overall_elo_rank2 = require_int(db[p2].get("EloRank"), "overall_elo_rank_2")

                surface_elo_rank1 = require_int(db[p1].get(rank_col), "surface_elo_rank_1")
                surface_elo_rank2 = require_int(db[p2].get(rank_col), "surface_elo_rank_2")

                overall_elo1 = require_float(db[p1].get("Elo"), "overall_elo_1")
                overall_elo2 = require_float(db[p2].get("Elo"), "overall_elo_2")

                surface_elo1 = require_float(db[p1].get(surface_elo_col), "surface_elo_1")
                surface_elo2 = require_float(db[p2].get(surface_elo_col), "surface_elo_2")

            except (TypeError, ValueError, KeyError) as exc:
                add_skipped(
                    skipped,
                    stats,
                    row,
                    "missing_or_invalid_elo_value",
                    str(exc),
                )
                continue

            ranking_favorite = p1 if rank1 < rank2 else p2
            elo_favorite = p1 if surface_elo1 > surface_elo2 else p2

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
                "Overall Elo Rank 1": overall_elo_rank1,
                "Overall Elo Rank 2": overall_elo_rank2,
                "Surface Elo Rank 1": surface_elo_rank1,
                "Surface Elo Rank 2": surface_elo_rank2,
                "Overall Elo 1": round(overall_elo1, 1),
                "Overall Elo 2": round(overall_elo2, 1),
                "Surface Elo 1": round(surface_elo1, 1),
                "Surface Elo 2": round(surface_elo2, 1),
                "Overall Elo Diff": round(abs(overall_elo1 - overall_elo2), 1),
                "Surface Elo Diff": round(abs(surface_elo1 - surface_elo2), 1),
                "Ranking Favorite": ranking_favorite,
                "ELO Favorite": elo_favorite,
            })

            stats["included_matches"] += 1

    rows_out.sort(key=lambda x: x["Surface Elo Diff"], reverse=True)

    output_fieldnames = [
        "DateLabel", "Tour", "Tournament", "Surface", "Time",
        "Player 1", "Player 2",
        "Rank 1", "Rank 2", "Rank Diff",
        "Overall Elo Rank 1", "Overall Elo Rank 2",
        "Surface Elo Rank 1", "Surface Elo Rank 2",
        "Overall Elo 1", "Overall Elo 2",
        "Surface Elo 1", "Surface Elo 2",
        "Overall Elo Diff", "Surface Elo Diff",
        "Ranking Favorite", "ELO Favorite",
    ]

    write_csv(OUTPUT_FILE, rows_out, output_fieldnames)

    mismatches = [
        row for row in rows_out
        if row["Ranking Favorite"] != row["ELO Favorite"]
    ]
    mismatches.sort(key=lambda x: x["Surface Elo Diff"], reverse=True)
    write_csv(MISMATCH_FILE, mismatches, output_fieldnames)

    skipped_fieldnames = [
        "DateLabel", "Tour", "Tournament", "Surface", "Time",
        "Player 1", "Player 2", "Reason", "Detail",
    ]
    write_csv(SKIPPED_FILE, skipped, skipped_fieldnames)

    print()
    print("=" * 50)
    print("FLASHSCORE -> ELO DIAGNOSTIKA")
    print("=" * 50)
    print(f"Načítaných zápasov:              {stats['loaded_matches']}")
    print(f"Výsledných zápasov:              {stats['included_matches']}")
    print(f"Vyradených zápasov:              {len(skipped)}")
    print()
    print("Dôvody vyradenia:")

    reason_keys = [
        "missing_player_1_name",
        "missing_player_2_name",
        "player_1_not_in_name_map",
        "player_2_not_in_name_map",
        "tour_mismatch",
        "unknown_tour",
        "player_1_not_in_elo_database",
        "player_2_not_in_elo_database",
        "unknown_surface",
        "missing_or_invalid_elo_value",
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
    print(f"Ranking vs ELO mismatch:         {len(mismatches)}")
    print(f"Výstup:                          {OUTPUT_FILE}")
    print(f"Mismatch výstup:                 {MISMATCH_FILE}")
    print(f"Diagnostika vyradených zápasov:  {SKIPPED_FILE}")
    print("=" * 50)


if __name__ == "__main__":
    main()
