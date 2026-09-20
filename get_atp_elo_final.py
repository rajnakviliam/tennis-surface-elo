import csv
import time
import requests
from bs4 import BeautifulSoup


URL = "https://tennisabstract.com/reports/atp_elo_ratings.html"
OUTPUT_FILE = "atp_elo.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


def download_table(max_attempts=5):
    session = requests.Session()
    session.headers.update(HEADERS)

    for attempt in range(1, max_attempts + 1):
        try:
            print(
                f"Tennis Abstract ATP Elo – "
                f"pokus {attempt}/{max_attempts}"
            )

            response = session.get(
                URL,
                timeout=30,
            )

            print(
                f"HTTP status: {response.status_code} | "
                f"HTML: {len(response.content)} bytes"
            )

            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            table = soup.find(
                "table",
                {"id": "reportable"},
            )

            if table is None:
                raise RuntimeError(
                    "Tabuľka #reportable nebola nájdená."
                )

            tbody = table.find("tbody")

            if tbody is None:
                raise RuntimeError(
                    "V Elo tabuľke nebolo nájdené tbody."
                )

            rows = tbody.find_all("tr")

            if len(rows) < 50:
                raise RuntimeError(
                    f"Našlo sa iba {len(rows)} riadkov. "
                    "Odpoveď pravdepodobne nie je kompletná."
                )

            print(
                f"ATP Elo tabuľka nájdená: "
                f"{len(rows)} riadkov."
            )

            return rows

        except (
            requests.RequestException,
            RuntimeError,
        ) as error:

            print(
                f"Pokus {attempt} zlyhal: {error}"
            )

            if attempt < max_attempts:
                wait_seconds = attempt * 5

                print(
                    f"Čakám {wait_seconds} sekúnd "
                    "a skúšam znova..."
                )

                time.sleep(wait_seconds)

    raise RuntimeError(
        "Tennis Abstract ATP Elo sa nepodarilo "
        f"načítať ani po {max_attempts} pokusoch. "
        "Pôvodný atp_elo.csv zostal nezmenený."
    )


rows = download_table()

players = []

for row in rows:
    cells = [
        c.get_text(" ", strip=True).replace("\xa0", " ")
        for c in row.find_all("td")
    ]

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
        "Rank": cells[15],
    })


if len(players) < 50:
    raise RuntimeError(
        f"Spracovalo sa iba {len(players)} ATP hráčov. "
        "atp_elo.csv sa preto neprepíše."
    )


with open(
    OUTPUT_FILE,
    "w",
    newline="",
    encoding="utf-8-sig",
) as f:

    fieldnames = [
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
    ]

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames,
        delimiter=";",
    )

    writer.writeheader()
    writer.writerows(players)


print(
    f"Hotovo. Uložených ATP hráčov: {len(players)}"
)
print(f"Súbor: {OUTPUT_FILE}")

for p in players[:20]:
    print(
        p["Player"],
        "| ATP:", p["Rank"],
        "| EloRank:", p["EloRank"],
        "| Hard:", p["HardEloRank"],
        "| Clay:", p["ClayEloRank"],
        "| Grass:", p["GrassEloRank"],
    )
