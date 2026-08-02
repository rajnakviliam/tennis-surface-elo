import csv
import os
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup


URL = "https://tennisabstract.com/reports/atp_elo_ratings.html"

OUTPUT_FILE = Path("atp_elo.csv")
TEMP_FILE = Path("atp_elo.tmp.csv")
DEBUG_FILE = Path("atp_elo_debug.html")

MAX_ATTEMPTS = 5
TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


def download_html():
    session = requests.Session()
    session.headers.update(HEADERS)

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(
                f"Sťahujem ATP Elo – pokus "
                f"{attempt}/{MAX_ATTEMPTS}..."
            )

            response = session.get(
                URL,
                timeout=TIMEOUT,
            )

            response.raise_for_status()

            html = response.text

            soup = BeautifulSoup(
                html,
                "html.parser",
            )

            table = soup.find(
                "table",
                {"id": "reportable"},
            )

            if table is None:
                raise RuntimeError(
                    "V odpovedi sa nenašla tabuľka "
                    "s id='reportable'."
                )

            tbody = table.find("tbody")

            if tbody is None:
                raise RuntimeError(
                    "V tabuľke sa nenašiel element tbody."
                )

            rows = tbody.find_all("tr")

            if not rows:
                raise RuntimeError(
                    "Tabuľka neobsahuje žiadne riadky."
                )

            return html, rows

        except (
            requests.RequestException,
            RuntimeError,
        ) as error:
            last_error = error

            try:
                if "response" in locals():
                    DEBUG_FILE.write_text(
                        response.text,
                        encoding="utf-8",
                    )
            except Exception:
                pass

            print(f"  Neúspešný pokus: {error}")

            if attempt < MAX_ATTEMPTS:
                wait_seconds = attempt * 5

                print(
                    f"  Ďalší pokus o "
                    f"{wait_seconds} sekúnd..."
                )

                time.sleep(wait_seconds)

    raise RuntimeError(
        f"ATP Elo sa nepodarilo stiahnuť ani po "
        f"{MAX_ATTEMPTS} pokusoch. "
        f"Posledná chyba: {last_error}. "
        f"Diagnostika: {DEBUG_FILE}"
    )


def parse_players(rows):
    players = []

    for row in rows:
        cells = [
            cell.get_text(
                " ",
                strip=True,
            ).replace("\xa0", " ")
            for cell in row.find_all("td")
        ]

        if len(cells) < 17:
            continue

        player_name = " ".join(
            cells[1].split()
        )

        if not player_name:
            continue

        players.append({
            "Player": player_name,
            "Tour": "ATP",
            "Rank": cells[15],
            "EloRank": cells[0],
            "Elo": cells[3],
            "HardEloRank": cells[5],
            "HardElo": cells[6],
            "ClayEloRank": cells[7],
            "ClayElo": cells[8],
            "GrassEloRank": cells[9],
            "GrassElo": cells[10],
        })

    if not players:
        raise RuntimeError(
            "Tabuľka sa našla, ale nepodarilo sa "
            "z nej načítať žiadnych hráčov."
        )

    return players


def write_players(players):
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

    with TEMP_FILE.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            delimiter=";",
        )

        writer.writeheader()
        writer.writerows(players)

    # Pôvodný súbor sa nahradí až po úspešnom zápise.
    os.replace(
        TEMP_FILE,
        OUTPUT_FILE,
    )


def main():
    try:
        _, rows = download_html()
        players = parse_players(rows)
        write_players(players)

    except Exception as error:
        print()
        print("=" * 60)
        print("CHYBA PRI AKTUALIZÁCII ATP ELO")
        print("=" * 60)
        print(error)
        print()
        print(
            "Pôvodný atp_elo.csv zostal zachovaný."
        )
        print("=" * 60)

        raise SystemExit(1)

    print()
    print("=" * 60)
    print("ATP ELO")
    print("=" * 60)
    print(
        f"Hotovo. Uložených ATP hráčov: "
        f"{len(players)}"
    )
    print(f"Súbor: {OUTPUT_FILE}")
    print("=" * 60)

    for player in players[:20]:
        print(
            player["Player"],
            "| ATP:", player["Rank"],
            "| EloRank:", player["EloRank"],
            "| Hard:", player["HardEloRank"],
            "| Clay:", player["ClayEloRank"],
            "| Grass:", player["GrassEloRank"],
        )


if __name__ == "__main__":
    main()
