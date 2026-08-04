from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials


SHEET_ID = "1jCNYJox7NnrCnjNxg_qKJNUSSwfIRUNnrf9o4do_R-0"
TIMEZONE = ZoneInfo("Europe/Bratislava")
KEEP_DAYS = 4


def get_worksheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    service_account_info = dict(
        st.secrets["gcp_service_account"]
    )

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes,
    )

    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(SHEET_ID)

    return spreadsheet.sheet1


def normalize_part(value):
    return " ".join(
        str(value or "")
        .replace("\xa0", " ")
        .strip()
        .lower()
        .split()
    )


def make_match_id(row):
    """
    Stabilné ID zápasu bez DateLabel a času.

    Zápas preto zostane rovnaký aj pri presune:
    Day+1 -> Today alebo pri zmene plánovaného času.
    """
    player_1 = normalize_part(row["Player 1"])
    player_2 = normalize_part(row["Player 2"])
    players = sorted([player_1, player_2])

    return "|".join(
        [
            normalize_part(row["Tour"]),
            normalize_part(row["Tournament"]),
            players[0],
            players[1],
        ]
    )


def parse_seen_at(value):
    value = str(value or "").strip()

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TIMEZONE)

    return parsed.astimezone(TIMEZONE)


def load_seen_matches():
    """
    Vráti slovník:
        match_id -> first_seen datetime

    Staré riadky bez first_seen sa považujú za videné
    a pri najbližšom zápise dostanú aktuálny čas.
    """
    worksheet = get_worksheet()
    values = worksheet.get_all_values()

    if not values:
        return {}

    headers = [
        str(value).strip().lower()
        for value in values[0]
    ]

    try:
        match_id_index = headers.index("match_id")
    except ValueError:
        match_id_index = 0

    first_seen_index = (
        headers.index("first_seen")
        if "first_seen" in headers
        else None
    )

    now = datetime.now(TIMEZONE)
    seen = {}

    for row in values[1:]:
        if len(row) <= match_id_index:
            continue

        match_id = str(row[match_id_index]).strip()

        if not match_id:
            continue

        first_seen = None

        if (
            first_seen_index is not None
            and len(row) > first_seen_index
        ):
            first_seen = parse_seen_at(
                row[first_seen_index]
            )

        seen[match_id] = first_seen or now

    return seen


def save_seen_matches(seen_matches):
    worksheet = get_worksheet()

    rows = [["match_id", "first_seen"]]

    for match_id, first_seen in sorted(
        seen_matches.items(),
        key=lambda item: (
            item[1],
            item[0],
        ),
    ):
        rows.append(
            [
                match_id,
                first_seen.astimezone(
                    TIMEZONE
                ).isoformat(
                    timespec="seconds"
                ),
            ]
        )

    worksheet.clear()
    worksheet.update(
        values=rows,
        range_name="A1",
    )


def compare_and_replace(df):
    """
    1. Načíta zápasy videné počas posledných 4 dní.
    2. Označí aktuálne neznáme MatchID ako nové.
    3. Pridá aktuálne zápasy do evidencie.
    4. Vymaže iba záznamy staršie než 4 dni.
    """
    result = df.copy()

    result["MatchID"] = result.apply(
        make_match_id,
        axis=1,
    )

    now = datetime.now(TIMEZONE)
    cutoff = now - timedelta(days=KEEP_DAYS)

    all_seen = load_seen_matches()

    recent_seen = {
        match_id: first_seen
        for match_id, first_seen in all_seen.items()
        if first_seen >= cutoff
    }

    result["IsNew"] = ~result["MatchID"].isin(
        recent_seen
    )

    for match_id in result["MatchID"].astype(str):
        if match_id not in recent_seen:
            recent_seen[match_id] = now

    save_seen_matches(recent_seen)

    return result
