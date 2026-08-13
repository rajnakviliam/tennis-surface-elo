import csv
from pathlib import Path


ATP_RANKINGS_FILE = Path("atp_rankings.csv")
WTA_RANKINGS_FILE = Path("wta_rankings.csv")
ATP_ELO_FILE = Path("atp_elo.csv")
WTA_ELO_FILE = Path("wta_elo.csv")

OUTPUT_FILE = Path("players_master.csv")

FIELDNAMES = [
    "Player",
    "Tour",
    "Rank",
    "EloRank",
    "Elo",
    "HardEloRank",
    "HardElo",
    "ClayEloRank",
    "ClayElo",
    "GrassEloRank",
    "GrassElo",
    "InRankings",
    "InElo",
]


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Súbor neexistuje: {path}")

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        return list(
            csv.DictReader(
                file,
                delimiter=";",
            )
        )


def clean(value) -> str:
    return " ".join(
        str(value or "")
        .replace("\xa0", " ")
        .split()
    )


def build_tour_master(
    rankings_rows: list[dict],
    elo_rows: list[dict],
    tour: str,
) -> list[dict]:
    players = {}

    for row in rankings_rows:
        player = clean(row.get("Player"))

        if not player:
            continue

        players[player] = {
            "Player": player,
            "Tour": tour,
            "Rank": clean(row.get("Rank")),
            "EloRank": "",
            "Elo": "",
            "HardEloRank": "",
            "HardElo": "",
            "ClayEloRank": "",
            "ClayElo": "",
            "GrassEloRank": "",
            "GrassElo": "",
            "InRankings": "True",
            "InElo": "False",
        }

    for row in elo_rows:
        player = clean(row.get("Player"))

        if not player:
            continue

        if player not in players:
            players[player] = {
                "Player": player,
                "Tour": tour,
                "Rank": clean(row.get("Rank")),
                "EloRank": "",
                "Elo": "",
                "HardEloRank": "",
                "HardElo": "",
                "ClayEloRank": "",
                "ClayElo": "",
                "GrassEloRank": "",
                "GrassElo": "",
                "InRankings": "False",
                "InElo": "True",
            }
        else:
            players[player]["InElo"] = "True"

        target = players[player]

        if not target["Rank"]:
            target["Rank"] = clean(row.get("Rank"))

        for column in (
            "EloRank",
            "Elo",
            "HardEloRank",
            "HardElo",
            "ClayEloRank",
            "ClayElo",
            "GrassEloRank",
            "GrassElo",
        ):
            target[column] = clean(row.get(column))

    return list(players.values())


def rank_sort_value(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 10**9


def main():
    atp_rankings = load_csv(ATP_RANKINGS_FILE)
    wta_rankings = load_csv(WTA_RANKINGS_FILE)
    atp_elo = load_csv(ATP_ELO_FILE)
    wta_elo = load_csv(WTA_ELO_FILE)

    atp_master = build_tour_master(
        atp_rankings,
        atp_elo,
        "ATP",
    )
    wta_master = build_tour_master(
        wta_rankings,
        wta_elo,
        "WTA",
    )

    rows = atp_master + wta_master

    rows.sort(
        key=lambda row: (
            row["Tour"],
            rank_sort_value(row["Rank"]),
            row["Player"].lower(),
        )
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=FIELDNAMES,
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(rows)

    atp_only_elo = sum(
        1
        for row in atp_master
        if row["InRankings"] == "False"
        and row["InElo"] == "True"
    )
    wta_only_elo = sum(
        1
        for row in wta_master
        if row["InRankings"] == "False"
        and row["InElo"] == "True"
    )

    print("=" * 64)
    print("PLAYERS MASTER")
    print("=" * 64)
    print(f"ATP hráči spolu:                {len(atp_master)}")
    print(f"WTA hráčky spolu:               {len(wta_master)}")
    print(f"Spolu hráčov:                   {len(rows)}")
    print(f"ATP iba v Elo:                  {atp_only_elo}")
    print(f"WTA iba v Elo:                  {wta_only_elo}")
    print(f"Výstup:                         {OUTPUT_FILE}")
    print("=" * 64)


if __name__ == "__main__":
    main()
