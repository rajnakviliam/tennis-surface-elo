import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


SHEET_ID = "1jCNYJox7NnrCnjNxg_qKJNUSSwfIRUNnrf9o4do_R-0"


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
    player_1 = normalize_part(row["Player 1"])
    player_2 = normalize_part(row["Player 2"])

    players = sorted([player_1, player_2])

    parts = [
        normalize_part(row["Tour"]),
        normalize_part(row["Tournament"]),
        players[0],
        players[1],
    ]

    return "|".join(parts)


def load_seen_matches():
    worksheet = get_worksheet()
    values = worksheet.get_all_values()

    if not values:
        return set()

    seen = set()

    for row in values[1:]:
        if not row:
            continue

        match_id = str(row[0]).strip()

        if match_id:
            seen.add(match_id)

    return seen


def replace_seen_matches(match_ids):
    worksheet = get_worksheet()

    unique_ids = sorted(
        {
            str(match_id).strip()
            for match_id in match_ids
            if str(match_id).strip()
        }
    )

    rows = [["match_id"]]
    rows.extend([[match_id] for match_id in unique_ids])

    worksheet.clear()
    worksheet.update(
        values=rows,
        range_name="A1",
    )


def compare_and_replace(df):
    result = df.copy()

    result["MatchID"] = result.apply(
        make_match_id,
        axis=1,
    )

    seen = load_seen_matches()

    result["IsNew"] = ~result["MatchID"].isin(seen)

    replace_seen_matches(
        result["MatchID"].tolist()
    )

    return result
