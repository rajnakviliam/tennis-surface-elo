import csv
import re
from pathlib import Path

from playwright.sync_api import sync_playwright


URL = "https://www.flashscore.com/tennis/"
OUT_FILE = "flashscore_matches.csv"

RAW_DIR = Path("data/raw_flashscore")
RAW_DIR.mkdir(parents=True, exist_ok=True)

SURFACE_MAP = {
    "hard": "hard",
    "clay": "clay",
    "grass": "grass",
    "indoor": "hard",
}


def clean(text):
    return " ".join(
        str(text or "")
        .replace("\xa0", " ")
        .split()
    ).strip()


def is_time(text):
    return bool(
        re.fullmatch(
            r"\d{1,2}:\d{2}",
            clean(text),
        )
    )


def parse_tournament_line(line):
    line = clean(line)

    m = re.match(
        r"^(.+?),\s*(hard|clay|grass|indoor)$",
        line,
        re.IGNORECASE,
    )

    if not m:
        return None

    tournament = clean(m.group(1))
    surface_raw = m.group(2).lower()
    surface = SURFACE_MAP.get(surface_raw, surface_raw)

    return tournament, surface


def parse_tour_line(line):
    line = clean(line)
    upper = line.upper()

    if "SINGLES" not in upper:
        return None

    if "DOUBLES" in upper or "UTR" in upper:
        return None

    if (
        "WTA" in upper
        or "WOMEN" in upper
        or "GIRLS" in upper
    ):
        return "WTA"

    return "ATP"


def parse_body_text(text, date_label):
    lines = [
        clean(line)
        for line in text.splitlines()
        if clean(line)
    ]

    rows = []
    current_tournament = ""
    current_surface = ""
    current_tour = ""

    i = 0

    while i < len(lines):
        line = lines[i]

        tournament_info = parse_tournament_line(line)

        if tournament_info:
            current_tournament, current_surface = tournament_info
            current_tour = ""
            i += 1
            continue

        tour = parse_tour_line(line)

        if tour:
            current_tour = tour
            i += 1
            continue

        if (
            is_time(line)
            and current_tournament
            and current_surface
            and current_tour
        ):
            if i + 2 >= len(lines):
                i += 1
                continue

            player1 = clean(lines[i + 1])
            player2 = clean(lines[i + 2])

            blocked = {
                "DRAW",
                "PREVIEW",
                "FINISHED",
                "CANCELLED",
                "POSTPONED",
            }

            if (
                not player1
                or not player2
                or player1.upper() in blocked
                or player2.upper() in blocked
            ):
                i += 1
                continue

            if "/" in player1 or "/" in player2:
                i += 1
                continue

            rows.append(
                [
                    date_label,
                    current_tour,
                    current_tournament,
                    current_surface,
                    line,
                    player1,
                    player2,
                ]
            )

            i += 3
            continue

        i += 1

    return rows


def save_raw(page, label):
    safe_name = label.lower().replace("+", "_plus_")

    html = page.content()
    text = page.locator("body").inner_text()

    (RAW_DIR / f"{safe_name}.html").write_text(
        html,
        encoding="utf-8",
    )

    (RAW_DIR / f"{safe_name}.txt").write_text(
        text,
        encoding="utf-8",
    )

    return text


def click_next_day(page):
    try:
        button = page.locator(
            'button[data-day-picker-arrow="next"]'
        )

        if button.count() == 0:
            print("  Next day button nenájdený.")
            return False

        print(
            "  Next day button nájdený:",
            button.first.get_attribute("aria-label"),
        )

        button.first.click()
        page.wait_for_timeout(5000)
        return True

    except Exception as error:
        print(
            "  Chyba pri prepnutí na zajtra:",
            error,
        )
        return False


def main():
    all_matches = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            locale="en-US",
            timezone_id="Europe/Bratislava",
            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/127.0 Safari/537.36"
            ),
        )

        page = context.new_page()

        print("Sťahujem: Today")

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(5000)

        today_text = save_raw(page, "Today")
        today_matches = parse_body_text(
            today_text,
            "Today",
        )

        print(
            "  nájdených zápasov:",
            len(today_matches),
        )

        all_matches.extend(today_matches)

        print("Sťahujem: Day+1")

        if click_next_day(page):
            tomorrow_text = save_raw(
                page,
                "Day+1",
            )
            tomorrow_matches = parse_body_text(
                tomorrow_text,
                "Day+1",
            )

            print(
                "  nájdených zápasov:",
                len(tomorrow_matches),
            )

            all_matches.extend(tomorrow_matches)

        browser.close()

    unique_matches = []
    seen = set()

    for row in all_matches:
        key = (
            row[0],
            row[2],
            row[5],
            row[6],
        )

        if key in seen:
            continue

        seen.add(key)
        unique_matches.append(row)

    with open(
        OUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.writer(
            f,
            delimiter=";",
        )

        writer.writerow(
            [
                "DateLabel",
                "Tour",
                "Tournament",
                "Surface",
                "Time",
                "Player 1",
                "Player 2",
            ]
        )

        writer.writerows(unique_matches)

    print("Hotovo.")
    print("Zápasov:", len(unique_matches))
    print("Súbor:", OUT_FILE)


if __name__ == "__main__":
    main()
