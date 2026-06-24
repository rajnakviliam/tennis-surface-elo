import sys
import subprocess
import datetime
from datetime import datetime as dt

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

PYTHON = sys.executable
SHEET_ID = "1jCNYJox7NnrCnjNxg_qKJNUSSwfIRUNnrf9o4do_R-0"

st.set_page_config(page_title="Tennis Surface ELO Finder", layout="wide")

st.title("🎾 Tennis Surface ELO Finder v2")

st.markdown(
    """
    Mobilne prispôsobená aplikácia pre hľadanie zápasov, kde sa ATP/WTA ranking
    nezhoduje so Surface ELO rankingom.
    """
)


def clean_output(stdout):
    filtered_lines = []

    for line in stdout.splitlines():
        if line.startswith("Súbor:"):
            continue
        if " -> " in line:
            continue
        if " | ATP:" in line:
            continue
        if " | EloRank:" in line:
            continue

        filtered_lines.append(line)

    return "\n".join(filtered_lines)


def run_script(script):
    result = subprocess.run(
        [PYTHON, script],
        text=True,
        capture_output=True
    )

    output = clean_output(result.stdout)

    if output:
        st.text(output)

    if result.returncode == 0:
        st.success(f"{script} dokončený.")
    else:
        st.error(result.stderr)


def get_worksheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    service_account_info = {
        "type": st.secrets["gcp_service_account"]["type"],
        "project_id": st.secrets["gcp_service_account"]["project_id"],
        "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
        "private_key": st.secrets["gcp_service_account"]["private_key"],
        "client_email": st.secrets["gcp_service_account"]["client_email"],
        "client_id": st.secrets["gcp_service_account"]["client_id"],
        "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
        "token_uri": st.secrets["gcp_service_account"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"],
        "universe_domain": st.secrets["gcp_service_account"]["universe_domain"],
    }

    creds = Credentials.from_service_account_info(
        service_account_info,
        scopes=scopes,
)

    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID)
    return sheet.sheet1


def load_seen_matches():
    worksheet = get_worksheet()
    records = worksheet.get_all_records()

    seen = set()
    for row in records:
        match_id = row.get("match_id")
        if match_id:
            seen.add(match_id)

    return seen


def save_new_matches(match_ids):
    if not match_ids:
        return

    worksheet = get_worksheet()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = [[match_id, now] for match_id in match_ids]
    worksheet.append_rows(rows)


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


st.subheader("1. Aktualizácia dát")

col1, col2 = st.columns(2)

with col1:
    if st.button("🎾 Flashscore zápasy"):
        run_script("export_flashscore_matches.py")

with col2:
    if st.button("🎯 ELO porovnanie"):
        run_script("flashscore_elo_compare.py")

col3, col4, col5 = st.columns(3)

with col3:
    if st.button("📊 ATP ELO"):
        run_script("get_atp_elo_final.py")

with col4:
    if st.button("📊 WTA ELO"):
        run_script("get_wta_elo_final.py")

with col5:
    if st.button("🧩 Mapa mien"):
        run_script("create_name_map.py")


st.subheader("2. Kompletná aktualizácia")

if st.button("🔄 Aktualizovať všetko"):
    scripts = [
        "export_flashscore_matches.py",
        "get_atp_elo_final.py",
        "get_wta_elo_final.py",
        "create_name_map.py",
        "flashscore_elo_compare.py",
    ]

    for script in scripts:
        st.write(f"Spúšťam: {script}")

        result = subprocess.run(
            [PYTHON, script],
            text=True,
            capture_output=True
        )

        output = clean_output(result.stdout)

        if output:
            st.text(output)

        if result.returncode != 0:
            st.error(result.stderr)
            st.stop()

    st.success("Všetko aktualizované.")


st.subheader("📊 Ranking vs Surface ELO mismatch")

try:
    df = pd.read_csv("ranking_vs_elo_mismatch.csv", sep=";")

    if df.empty:
        st.info("Žiadne ranking vs Surface ELO mismatch zápasy.")
    else:
        date_options = sorted(df["DateLabel"].dropna().unique())
        tour_options = sorted(df["Tour"].dropna().unique())
        surface_options = sorted(df["Surface"].dropna().unique())

        selected_dates = st.multiselect("Dni", date_options, default=date_options)
        selected_tours = st.multiselect("Tour", tour_options, default=tour_options)
        selected_surfaces = st.multiselect("Povrch", surface_options, default=surface_options)

        df_view = df[
            df["DateLabel"].isin(selected_dates)
            & df["Tour"].isin(selected_tours)
            & df["Surface"].isin(selected_surfaces)
        ].copy()

        def day_order(value):
            if value == "Today":
                return 0
            if str(value).startswith("Day+"):
                return int(str(value).replace("Day+", ""))
            return 99

        now_time = dt.now().time()

        df_view["DayOrder"] = df_view["DateLabel"].apply(day_order)
        df_view["MatchTime"] = pd.to_datetime(
            df_view["Time"],
            format="%H:%M",
            errors="coerce"
        ).dt.time

        df_view = df_view[
            ~(
                (df_view["DateLabel"] == "Today")
                & (df_view["MatchTime"] < now_time)
            )
        ]

        df_view = df_view.sort_values(
            by=["DayOrder", "Time"],
            ascending=[True, True]
        )

        try:
            seen_matches = load_seen_matches()

            df_view["match_id"] = df_view.apply(make_match_id, axis=1)
            df_view["IsNew"] = ~df_view["match_id"].isin(seen_matches)

            new_match_ids = df_view[df_view["IsNew"]]["match_id"].tolist()
            save_new_matches(new_match_ids)

        except Exception as e:
            import traceback
            st.code(traceback.format_exc())
            st.warning(f"Nepodarilo sa pripojiť ku Google Sheet: {repr(e)}")
            df_view["IsNew"] = True

        show_new_only = st.checkbox("🆕 Zobraziť iba nové zápasy")

        if show_new_only:
            df_view = df_view[df_view["IsNew"]]

        st.caption(
            f"Počet zápasov: {len(df_view)} | Nové: {df_view['IsNew'].sum()}"
        )

        for _, row in df_view.iterrows():
            new_badge = "🆕 " if row.get("IsNew", False) else ""
            elo_fav = row["ELO Favorite"]
            ranking_fav = row["Ranking Favorite"]

            if elo_fav == row["Player 1"]:
                elo_text = f"🟦 Surface ELO → {elo_fav}"
            else:
                elo_text = f"🟧 Surface ELO → {elo_fav}"

            st.markdown(
                f"""
### {new_badge}{row["DateLabel"]} · {row["Time"]}

🎾 **{row["Player 1"]}** vs **{row["Player 2"]}**

**Ranking favorit:** {ranking_fav}  
**Rank rozdiel:** {row["Rank Diff"]}

**{elo_text}**  
**ELO rozdiel:** {row["ELO Diff"]}
"""
            )

            with st.expander("📊 Detail zápasu"):
                col_a, col_b = st.columns(2)

                with col_a:
                    st.markdown(f"#### 🟦 {row['Player 1']}")
                    st.write(f"Rank: {row['Rank 1']}")
                    st.write(f"Surface ELO Rank: {row['Surface Elo Rank 1']}")

                with col_b:
                    st.markdown(f"#### 🟧 {row['Player 2']}")
                    st.write(f"Rank: {row['Rank 2']}")
                    st.write(f"Surface ELO Rank: {row['Surface Elo Rank 2']}")

                st.markdown("---")
                st.write(f"Ranking favorit: {ranking_fav}")
                st.write(f"Surface ELO favorit: {elo_fav}")
                st.write(f"Rank rozdiel: {row['Rank Diff']}")
                st.write(f"ELO rozdiel: {row['ELO Diff']}")

            st.divider()

        csv = df_view.to_csv(index=False, sep=";").encode("utf-8-sig")

        st.download_button(
            "⬇️ Stiahnuť mismatch CSV",
            csv,
            "ranking_vs_elo_mismatch.csv",
            "text/csv"
        )

except FileNotFoundError:
    st.info("Najprv spusti ELO porovnanie.")


with st.expander("📋 Všetky analyzované zápasy"):
    try:
        df_all = pd.read_csv("flashscore_elo_matches.csv", sep=";")

        if df_all.empty:
            st.info("Zatiaľ nie sú dostupné analyzované zápasy.")
        else:
            df_all = df_all.sort_values(
                by="ELO Diff",
                ascending=False
            )

            st.dataframe(
                df_all,
                use_container_width=True,
                hide_index=True
            )

    except FileNotFoundError:
        st.info("Súbor flashscore_elo_matches.csv zatiaľ neexistuje.")