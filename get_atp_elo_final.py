import csv
import requests
from bs4 import BeautifulSoup

url = "https://tennisabstract.com/reports/atp_elo_ratings.html"
headers = {"User-Agent": "Mozilla/5.0"}

html = requests.get(url, headers=headers, timeout=20).text
soup = BeautifulSoup(html, "html.parser")

table = soup.find("table", {"id": "reportable"})

rows = table.find("tbody").find_all("tr")

players = []

for row in rows:
    cells = [c.get_text(" ", strip=True).replace("\xa0", " ") for c in row.find_all("td")]

    if len(cells) < 17:
        continue

    players.append({
        "Player": cells[1],
        "Tour": "ATP",
        "EloRank": cells[0],
        "Elo": cells[3],
        "HardEloRank": cells[5],
        "HardElo": cells[6],
        "ClayEloRank": cells[7],
        "ClayElo": cells[8],
        "GrassEloRank": cells[9],
        "GrassElo": cells[10],
        "Rank": cells[15]
    })

with open("atp_elo.csv", "w", newline="", encoding="utf-8-sig") as f:
    fieldnames = [
        "Player", "Tour", "Rank",
        "EloRank", "Elo",
        "HardEloRank", "HardElo",
        "ClayEloRank", "ClayElo",
        "GrassEloRank", "GrassElo"
    ]

    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
    writer.writeheader()
    writer.writerows(players)

print(f"Hotovo. Uložených ATP hráčov: {len(players)}")
print("Súbor: atp_elo.csv")

for p in players[:20]:
    print(
        p["Player"],
        "| ATP:", p["Rank"],
        "| EloRank:", p["EloRank"],
        "| Hard:", p["HardEloRank"],
        "| Clay:", p["ClayEloRank"],
        "| Grass:", p["GrassEloRank"]
    )