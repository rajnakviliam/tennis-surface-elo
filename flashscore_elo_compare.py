import csv

# -----------------------------
# načítanie ATP
# -----------------------------

atp = {}

with open("atp_elo.csv", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f, delimiter=";")

    for row in reader:
        atp[row["Player"]] = row


# -----------------------------
# načítanie WTA
# -----------------------------

wta = {}

with open("wta_elo.csv", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f, delimiter=";")

    for row in reader:
        wta[row["Player"]] = row


# -----------------------------
# name map
# -----------------------------

name_map = {}

with open("name_map.csv", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f, delimiter=";")

    for row in reader:
        name_map[row["TE_Name"]] = {
            "TA_Name": row["TA_Name"],
            "Tour": row["Tour"]
        }


surface_rank_column = {
    "hard": "HardEloRank",
    "clay": "ClayEloRank",
    "grass": "GrassEloRank"
}

surface_elo_column = {
    "hard": "HardElo",
    "clay": "ClayElo",
    "grass": "GrassElo"
}


rows_out = []

with open("flashscore_matches.csv", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f, delimiter=";")

    for row in reader:
        p1_te = row["Player 1"]
        p2_te = row["Player 2"]

        if p1_te not in name_map:
            continue

        if p2_te not in name_map:
            continue

        p1 = name_map[p1_te]["TA_Name"]
        p2 = name_map[p2_te]["TA_Name"]

        tour = name_map[p1_te]["Tour"]

        db = atp if tour == "ATP" else wta

        if p1 not in db:
            continue

        if p2 not in db:
            continue

        surface = row["Surface"].lower()

        if surface not in surface_rank_column:
            continue

        rank_col = surface_rank_column[surface]
        surface_elo_col = surface_elo_column[surface]

        try:
            rank1 = int(db[p1]["Rank"])
            rank2 = int(db[p2]["Rank"])

            overall_elo_rank1 = int(db[p1]["EloRank"])
            overall_elo_rank2 = int(db[p2]["EloRank"])

            surface_elo_rank1 = int(db[p1][rank_col])
            surface_elo_rank2 = int(db[p2][rank_col])

            overall_elo1 = float(db[p1]["Elo"])
            overall_elo2 = float(db[p2]["Elo"])

            surface_elo1 = float(db[p1][surface_elo_col])
            surface_elo2 = float(db[p2][surface_elo_col])

        except Exception:
            continue

        ranking_favorite = p1 if rank1 < rank2 else p2
        elo_favorite = p1 if surface_elo1 > surface_elo2 else p2

        rows_out.append({
            "DateLabel": row.get("DateLabel", ""),
            "Tour": tour,
            "Tournament": row["Tournament"],
            "Surface": surface,
            "Time": row["Time"],

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
            "ELO Favorite": elo_favorite
        })


if not rows_out:
    print("Hotovo.")
    print("Zápasov: 0")
    print("Neboli nájdené žiadne zápasy na porovnanie.")
    raise SystemExit


rows_out.sort(
    key=lambda x: x["Surface Elo Diff"],
    reverse=True
)


with open(
    "flashscore_elo_matches.csv",
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:
    fieldnames = list(rows_out[0].keys())

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames,
        delimiter=";"
    )

    writer.writeheader()
    writer.writerows(rows_out)


mismatches = []

for row in rows_out:
    if row["Ranking Favorite"] != row["ELO Favorite"]:
        mismatches.append(row)


mismatches.sort(
    key=lambda x: x["Surface Elo Diff"],
    reverse=True
)


with open(
    "ranking_vs_elo_mismatch.csv",
    "w",
    newline="",
    encoding="utf-8-sig"
) as f:
    fieldnames = list(rows_out[0].keys())

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames,
        delimiter=";"
    )

    writer.writeheader()
    writer.writerows(mismatches)


print("Ranking vs ELO mismatch:", len(mismatches))
print("Výstup: ranking_vs_elo_mismatch.csv")

print("Hotovo.")
print("Zápasov:", len(rows_out))
print("Výstup: flashscore_elo_matches.csv")