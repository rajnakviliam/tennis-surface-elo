import csv
from pathlib import Path

import requests
from bs4 import BeautifulSoup


URL = "https://tennisabstract.com/reports/wtaRankings.html"
OUTPUT_FILE = Path("wta_rankings.csv")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/150 Safari/537.36"
    )
}


def download_html() -> str:
    response = requests.get(
        URL,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def parse_rankings(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rankings = []

    for row in soup.select("table tr"):
        cells = row.find_all(["td", "th"])

        if len(cells) < 2:
            continue

        rank_text = cells[0].get_text(" ", strip=True)
        player = cells[1].get_text(" ", strip=True)
        
        player = " ".join(
            player.replace("\xa0", " ").split()
        )        

        try:
            rank = int(rank_text)
        except ValueError:
            continue

        if not player:
            continue

        rankings.append(
            {
                "Player": player,
                "Rank": rank,
                "Tour": "WTA",
            }
        )

    # Odstránenie prípadných duplicít podľa mena.
    unique = {}

    for row in rankings:
        player = row["Player"]

        if player not in unique:
            unique[player] = row
        elif row["Rank"] < unique[player]["Rank"]:
            unique[player] = row

    return sorted(
        unique.values(),
        key=lambda row: row["Rank"],
    )


def write_csv(rankings: list[dict]) -> None:
    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["Player", "Rank", "Tour"],
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(rankings)


def main() -> None:
    print("Sťahujem WTA ranking z Tennis Abstract...")

    try:
        html = download_html()
        rankings = parse_rankings(html)

        if not rankings:
            raise RuntimeError(
                "Na stránke sa nepodarilo nájsť žiadnych hráčov."
            )

        write_csv(rankings)

    except requests.RequestException as error:
        print(f"Chyba pri sťahovaní: {error}")
        raise SystemExit(1)

    except Exception as error:
        print(f"Chyba pri spracovaní: {error}")
        raise SystemExit(1)

    print("=" * 55)
    print("WTA RANKINGS")
    print("=" * 55)
    print(f"Načítaných hráčov: {len(rankings)}")
    print(f"Prvý hráč:         {rankings[0]['Player']}")
    print(f"Posledný ranking:  {rankings[-1]['Rank']}")
    print(f"Výstup:            {OUTPUT_FILE}")
    print("=" * 55)


if __name__ == "__main__":
    main()