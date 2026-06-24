import datetime
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


SHEET_ID = "1jCNYJox7NnrCnjNxg_qKJNUSSwfIRUNnrf9o4do_R-0"


def get_worksheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    service_account_info = dict(st.secrets["gcp_service_account"])

    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes,
    )

    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
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
        import traceback
        st.code(traceback.format_exc())
        st.warning(f"Nepodarilo sa načítať Google Sheet: {repr(e)}")


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
        import traceback
        st.code(traceback.format_exc())
        st.warning(f"Nepodarilo sa uložiť nové zápasy do Google Sheet: {repr(e)}")


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