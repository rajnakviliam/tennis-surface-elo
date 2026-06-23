import datetime
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


SHEET_NAME = "tennis_seen_matches"


def get_worksheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes,
    )

    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME)
    return sheet.sheet1


def load_seen_matches():
    try:
        worksheet = get_worksheet()
        records = worksheet.get_all_records()

        seen = set()
        for row in records:
            match_id = row.get("match_id")
            if match_id:
                seen.add(match_id)

        return seen

    except Exception as e:
        st.warning(f"Nepodarilo sa načítať Google Sheet: {e}")
        return set()


def save_new_matches(match_ids):
    if not match_ids:
        return

    try:
        worksheet = get_worksheet()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        rows = []
        for match_id in match_ids:
            rows.append([match_id, now])

        worksheet.append_rows(rows)

    except Exception as e:
        st.warning(f"Nepodarilo sa uložiť nové zápasy do Google Sheet: {e}")


def make_match_id(row):
    return (
        str(row["DateLabel"])
        + "|"
        + str(row["Time"])
        + "|"
        + str(row["Player 1"])
        + "|"
        + str(row["Player 2"])
    )