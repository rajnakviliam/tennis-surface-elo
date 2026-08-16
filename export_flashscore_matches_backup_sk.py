import requests
import csv
import re
from bs4 import BeautifulSoup
from pathlib import Path

headers = {
    "User-Agent": "Mozilla/5.0"
}

urls = [("Today", "https://m.flashscore.sk/tenis/")]

for d in range(1, 4):
    urls.append(
        (
            f"Day+{d}",
            f"https://m.flashscore.sk/tenis/?d={d}"
        )
    )

surface_map = {
    "tráva": "grass",
    "antuka": "clay",
    "tvrdý povrch": "hard"
}

all_matches = []

RAW_DIR = Path("data/raw_flashscore")
RAW_DIR.mkdir(parents=True, exist_ok=True)


def clean_flashscore_player(name):
    name = re.sub(r"\s*\([A-Za-z]{3}\)", "", name)
    name = name.replace(" SKREČ", "")
    name = name.replace("Zrušené", "")
    return name.strip()


for date_label, url in urls:
    print("Sťahujem:", date_label)

    before_count = len(all_matches)

    html = requests.get(url, headers=headers, timeout=20).text
    
    safe_name = date_label.lower().replace("+", "_plus_")

    html_path = RAW_DIR / f"{safe_name}.html"

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  HTML uložené: {html_path}")
    
    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text("\n", strip=True)
    
    text_path = RAW_DIR / f"{safe_name}.txt"

    with open(text_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"  TXT uložené : {text_path}")
    
    lines = text.splitlines()

    current_tour = ""
    current_tournament = ""
    current_surface = ""

    for i, line in enumerate(lines):
        line = line.strip()

        if "ŠTVORHRY" in line or "UTR" in line:
            current_tour = ""
            current_tournament = ""
            current_surface = ""
            continue

        m = re.search(
            r"(.+?)\s*-\s*DVOJHRY:\s*(.+?),\s*(tráva|antuka|tvrdý povrch)",
            line,
            re.IGNORECASE
        )

        if m:
            tour_text = m.group(1).upper()

            if "ŽENY" in tour_text or "WTA" in tour_text:
                current_tour = "WTA"
            else:
                current_tour = "ATP"

            current_tournament = m.group(2).strip()
            current_surface = surface_map.get(
                m.group(3).strip().lower(),
                m.group(3).strip().lower()
            )

            continue

        is_scheduled_time = re.match(
            r"^\d{1,2}:\d{2}$",
            line,
        )

        is_live_status = re.match(
            r"^(1\. set|2\. set|3\. set|Tiebreak)$",
            line,
            re.IGNORECASE,
        )

        if is_scheduled_time or is_live_status:
            if i + 1 >= len(lines):
                continue

            if not current_tour or not current_tournament or not current_surface:
                continue

            next_line = lines[i + 1].strip()

            if "Zrušené" in next_line:
                continue

            # Bežný formát:
            # Player 1 - Player 2
            if " - " in next_line:
                player1, player2 = next_line.split(" - ", 1)

            # Rozdelený formát:
            # Player 1 -
            # Player 2
            elif next_line.endswith(" -"):
                if i + 2 >= len(lines):
                    continue

                player1 = next_line[:-2].strip()
                player2 = lines[i + 2].strip()

            else:
                continue

            if "/" in player1 or "/" in player2:
                continue

            match_time = line if is_scheduled_time else ""

            all_matches.append([
                date_label,
                current_tour,
                current_tournament,
                current_surface,
                match_time,
                clean_flashscore_player(player1),
                clean_flashscore_player(player2),
            ])

    added = len(all_matches) - before_count
    print("  nájdených zápasov:", added)

# Odstránenie duplicít
unique_matches = []
seen = set()

for row in all_matches:

    key = (
        row[2],  # Tournament
        row[5],  # Player 1
        row[6],  # Player 2
    )

    if key not in seen:
        seen.add(key)
        unique_matches.append(row)

all_matches = unique_matches

with open("flashscore_matches.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f, delimiter=";")
    writer.writerow([
        "DateLabel",
        "Tour",
        "Tournament",
        "Surface",
        "Time",
        "Player 1",
        "Player 2"
    ])
    writer.writerows(all_matches)

print("Hotovo.")
print("Zápasov:", len(all_matches))
print("Súbor: flashscore_matches.csv")
