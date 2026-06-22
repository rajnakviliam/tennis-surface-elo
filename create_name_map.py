import csv

SURNAME_PREFIXES = {
    "de", "del", "de la", "da", "dos", "van", "von", "di", "du"
}

def make_te_names(full_name):
    parts = full_name.strip().split()

    if len(parts) < 2:
        return [full_name]

    first_initial = parts[0][0] + "."

    variants = set()

    # základný variant: všetko okrem prvého mena ako priezvisko
    variants.add(" ".join(parts[1:]) + " " + first_initial)

    # posledné slovo ako priezvisko
    variants.add(parts[-1] + " " + first_initial)

    # posledné dve slová ako priezvisko
    if len(parts) >= 3:
        variants.add(" ".join(parts[-2:]) + " " + first_initial)

    # posledné tri slová ako priezvisko
    if len(parts) >= 4:
        variants.add(" ".join(parts[-3:]) + " " + first_initial)

    # prípady typu Van Assche, De Minaur, De Almeida
    for i in range(1, len(parts) - 1):
        prefix = parts[i].lower()
        if prefix in SURNAME_PREFIXES:
            variants.add(" ".join(parts[i:]) + " " + first_initial)

    return sorted(variants)

def load_players(filename, tour):
    players = []

    with open(filename, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            full_name = row["Player"].strip()

            for te_name in make_te_names(full_name):
                players.append({
                    "TE_Name": te_name,
                    "TA_Name": full_name,
                    "Tour": tour
                })

    return players

all_players = []
all_players.extend(load_players("atp_elo.csv", "ATP"))
all_players.extend(load_players("wta_elo.csv", "WTA"))

# odstránenie duplicít
unique = {}
for p in all_players:
    key = (p["TE_Name"], p["Tour"])
    if key not in unique:
        unique[key] = p

all_players = list(unique.values())

with open("name_map.csv", "w", newline="", encoding="utf-8-sig") as f:
    fieldnames = ["TE_Name", "TA_Name", "Tour"]
    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
    writer.writeheader()
    writer.writerows(all_players)

print(f"Hotovo. Vytvorených mapovaní: {len(all_players)}")
print("Súbor: name_map.csv")

for p in all_players[:40]:
    print(p["TE_Name"], "->", p["TA_Name"], "|", p["Tour"])