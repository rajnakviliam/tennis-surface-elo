
import csv
from collections import Counter
from pathlib import Path

from name_matcher import build_player_records, match_name


SKIPPED_FILE = Path("skipped_matches.csv")
NAME_MAP_FILE = Path("name_map.csv")
ATP_FILE = Path("atp_elo.csv")
WTA_FILE = Path("wta_elo.csv")

AUTO_ADDED_FILE = Path("name_map_auto_added.csv")
MANUAL_REVIEW_FILE = Path("manual_review.csv")
UNMATCHED_FILE = Path("unmatched_names.csv")

AUTO_ADD_THRESHOLD = 99.0
MANUAL_REVIEW_THRESHOLD = 90.0


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def load_elo_players(path: Path, fallback_tour: str) -> list[tuple[str, str]]:
    players = []

    for row in read_csv(path):
        name = (row.get("Player") or "").strip()
        tour = (row.get("Tour") or fallback_tour).strip().upper()

        if name:
            players.append((name, tour))

    return players


def load_existing_name_map(path: Path) -> tuple[list[dict], set[tuple[str, str]]]:
    if not path.exists():
        return [], set()

    rows = []
    keys = set()

    for row in read_csv(path):
        te_name = (row.get("TE_Name") or "").strip()
        ta_name = (row.get("TA_Name") or "").strip()
        tour = (row.get("Tour") or "").strip().upper()

        if not te_name:
            continue

        rows.append({
            "TE_Name": te_name,
            "TA_Name": ta_name,
            "Tour": tour,
        })
        keys.add((te_name, tour))

    return rows, keys


def load_missing_players(path: Path) -> set[tuple[str, str]]:
    missing: set[tuple[str, str]] = set()

    for row in read_csv(path):
        reason = (row.get("Reason") or "").strip()
        tour = (row.get("Tour") or "").strip().upper()

        if reason == "player_1_not_in_name_map":
            name = (row.get("Player 1") or "").strip()
        elif reason == "player_2_not_in_name_map":
            name = (row.get("Player 2") or "").strip()
        else:
            continue

        if name and tour in {"ATP", "WTA"}:
            missing.add((name, tour))

    return missing


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter=";",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    existing_rows, existing_keys = load_existing_name_map(NAME_MAP_FILE)
    missing_players = load_missing_players(SKIPPED_FILE)

    atp_players = load_elo_players(ATP_FILE, "ATP")
    wta_players = load_elo_players(WTA_FILE, "WTA")
    candidates = build_player_records(atp_players + wta_players)

    auto_added = []
    manual_review = []
    unmatched = []

    matched_by_tour = Counter()
    unmatched_by_tour = Counter()

    for source_name, tour in sorted(missing_players, key=lambda x: (x[1], x[0].lower())):
        if (source_name, tour) in existing_keys:
            continue

        result = match_name(
            source_name=source_name,
            candidates=candidates,
            source_tour=tour,
            minimum_confidence=MANUAL_REVIEW_THRESHOLD,
        )

        if result.matched and result.confidence >= AUTO_ADD_THRESHOLD:
            auto_added.append({
                "TE_Name": source_name,
                "TA_Name": result.matched_name,
                "Tour": result.tour,
                "Confidence": result.confidence,
                "Reason": result.reason,
            })
            matched_by_tour[tour] += 1

        elif result.matched:
            manual_review.append({
                "TE_Name": source_name,
                "Suggested_TA_Name": result.matched_name,
                "Suggested_Tour": result.tour,
                "Confidence": result.confidence,
                "Reason": result.reason,
                "Decision": "",
            })

        else:
            unmatched.append({
                "TE_Name": source_name,
                "Tour": tour,
                "Confidence": result.confidence,
                "Reason": result.reason,
            })
            unmatched_by_tour[tour] += 1

    updated_name_map = list(existing_rows)
    updated_name_map.extend({
        "TE_Name": row["TE_Name"],
        "TA_Name": row["TA_Name"],
        "Tour": row["Tour"],
    } for row in auto_added)

    # Odstránenie prípadných duplicitných riadkov.
    deduplicated = {}
    for row in updated_name_map:
        deduplicated[(row["TE_Name"], row["Tour"])] = row

    updated_name_map = sorted(
        deduplicated.values(),
        key=lambda row: (row["Tour"], row["TE_Name"].lower()),
    )

    write_csv(NAME_MAP_FILE, updated_name_map, ["TE_Name", "TA_Name", "Tour"])
    write_csv(
        AUTO_ADDED_FILE,
        auto_added,
        ["TE_Name", "TA_Name", "Tour", "Confidence", "Reason"],
    )
    write_csv(
        MANUAL_REVIEW_FILE,
        manual_review,
        [
            "TE_Name",
            "Suggested_TA_Name",
            "Suggested_Tour",
            "Confidence",
            "Reason",
            "Decision",
        ],
    )
    write_csv(
        UNMATCHED_FILE,
        unmatched,
        ["TE_Name", "Tour", "Confidence", "Reason"],
    )

    print()
    print("=" * 60)
    print("NAME MAP BUILD REPORT V2")
    print("=" * 60)
    print(f"ATP Elo hráčov načítaných:       {len(atp_players)}")
    print(f"WTA Elo hráčok načítaných:       {len(wta_players)}")
    print(f"Existujúcich mapovaní:            {len(existing_rows)}")
    print(f"Chýbajúcich dvojíc meno/tour:     {len(missing_players)}")
    print(f"Automaticky pridaných:            {len(auto_added)}")
    print(f"  ATP:                            {matched_by_tour['ATP']}")
    print(f"  WTA:                            {matched_by_tour['WTA']}")
    print(f"Na manuálnu kontrolu:             {len(manual_review)}")
    print(f"Nenájdených:                      {len(unmatched)}")
    print(f"  ATP:                            {unmatched_by_tour['ATP']}")
    print(f"  WTA:                            {unmatched_by_tour['WTA']}")
    print()
    print(f"Aktualizovaný súbor:              {NAME_MAP_FILE}")
    print(f"Automaticky pridané:              {AUTO_ADDED_FILE}")
    print(f"Manuálna kontrola:                {MANUAL_REVIEW_FILE}")
    print(f"Nenájdené mená:                   {UNMATCHED_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
