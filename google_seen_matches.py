from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials


SHEET_ID = "1jCNYJox7NnrCnjNxg_qKJNUSSwfIRUNnrf9o4do_R-0"
TIMEZONE = ZoneInfo("Europe/Bratislava")
KEEP_DAYS = 4

SHEET_HEADERS = [
    "match_id",
    "first_seen",
    "last_seen",
    "is_new",
]


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
    Stabilné ID zápasu.

    Neobsahuje DateLabel ani čas, takže ten istý zápas
    zostane rovnaký pri presune Day+1 -> Today,
    Today -> Day+1 alebo pri zmene času.
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


def parse_datetime(value):
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


def parse_bool(value):
    return str(value or "").strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
        "áno",
        "ano",
    }


def load_match_states():
    """
    Vráti slovník:
        match_id -> {
            first_seen: datetime,
            last_seen: datetime,
            is_new: bool,
        }

    Podporuje aj staršiu tabuľku s jedným alebo dvoma stĺpcami.
    Staré riadky bez is_new sa považujú za videné.
    """
    worksheet = get_worksheet()
    values = worksheet.get_all_values()

    if not values:
        return {}

    headers = [
        str(value).strip().lower()
        for value in values[0]
    ]

    def column_index(name, fallback=None):
        try:
            return headers.index(name)
        except ValueError:
            return fallback

    match_id_index = column_index("match_id", 0)
    first_seen_index = column_index("first_seen")
    last_seen_index = column_index("last_seen")
    is_new_index = column_index("is_new")

    now = datetime.now(TIMEZONE)
    states = {}

    for row in values[1:]:
        if len(row) <= match_id_index:
            continue

        match_id = str(row[match_id_index]).strip()

        if not match_id:
            continue

        first_seen = (
            parse_datetime(row[first_seen_index])
            if first_seen_index is not None
            and len(row) > first_seen_index
            else None
        )

        last_seen = (
            parse_datetime(row[last_seen_index])
            if last_seen_index is not None
            and len(row) > last_seen_index
            else None
        )

        is_new = (
            parse_bool(row[is_new_index])
            if is_new_index is not None
            and len(row) > is_new_index
            else False
        )

        first_seen = first_seen or now
        last_seen = last_seen or first_seen

        states[match_id] = {
            "first_seen": first_seen,
            "last_seen": last_seen,
            "is_new": is_new,
        }

    return states


def save_match_states(states):
    worksheet = get_worksheet()

    rows = [SHEET_HEADERS]

    sorted_states = sorted(
        states.items(),
        key=lambda item: (
            item[1]["last_seen"],
            item[0],
        ),
        reverse=True,
    )

    for match_id, state in sorted_states:
        rows.append(
            [
                match_id,
                state["first_seen"].astimezone(
                    TIMEZONE
                ).isoformat(timespec="seconds"),
                state["last_seen"].astimezone(
                    TIMEZONE
                ).isoformat(timespec="seconds"),
                "TRUE" if state["is_new"] else "FALSE",
            ]
        )

    worksheet.clear()
    worksheet.update(
        values=rows,
        range_name="A1",
    )


def add_saved_status(df):
    """
    Iba načíta uložený stav z Google Sheets.
    Nič nezapisuje, takže otvorenie, rerun ani reštart
    aplikácie nemôžu zrušiť označenie NOVÉ.
    """
    result = df.copy()

    result["MatchID"] = result.apply(
        make_match_id,
        axis=1,
    )

    states = load_match_states()

    result["IsNew"] = result["MatchID"].map(
        lambda match_id: bool(
            states.get(
                match_id,
                {},
            ).get(
                "is_new",
                False,
            )
        )
    )

    return result


def update_after_refresh(df):
    """
    Volá sa iba po manuálnom kliknutí na Aktualizovať zápasy.

    - všetky dovtedy NOVÉ zápasy označí ako videné,
    - aktuálne neznáme zápasy označí ako NOVÉ,
    - aktualizuje last_seen pri dnešných a zajtrajších zápasoch,
    - odstráni iba zápasy, ktoré neboli v aktuálnom zozname
      viac než KEEP_DAYS dní,
    - stav uloží do Google Sheets.
    """
    result = df.copy()

    result["MatchID"] = result.apply(
        make_match_id,
        axis=1,
    )

    now = datetime.now(TIMEZONE)
    cutoff = now - timedelta(days=KEEP_DAYS)

    old_states = load_match_states()

    # Pred každou manuálnou aktualizáciou sa všetky predtým nové
    # zápasy považujú za už videné.
    for state in old_states.values():
        state["is_new"] = False

    current_ids = set(
        result["MatchID"].astype(str)
    )

    for match_id in current_ids:
        if match_id in old_states:
            old_states[match_id]["last_seen"] = now
        else:
            old_states[match_id] = {
                "first_seen": now,
                "last_seen": now,
                "is_new": True,
            }

    cleaned_states = {
        match_id: state
        for match_id, state in old_states.items()
        if (
            match_id in current_ids
            or state["last_seen"] >= cutoff
        )
    }

    save_match_states(cleaned_states)

    result["IsNew"] = result["MatchID"].map(
        lambda match_id: cleaned_states[
            match_id
        ]["is_new"]
    )

    return result
