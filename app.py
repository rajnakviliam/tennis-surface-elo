import sys
import subprocess
import datetime
from datetime import datetime as dt
from zoneinfo import ZoneInfo

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

PYTHON = sys.executable
SHEET_ID = "1jCNYJox7NnrCnjNxg_qKJNUSSwfIRUNnrf9o4do_R-0"

st.set_page_config(page_title="Tennis Surface ELO Finder", layout="wide")

st.title("🎾 Tennis Surface ELO Finder v4")

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


def make_match_id(row):
    players = sorted([
        str(row["Player 1"]).strip(),
        str(row["Player 2"]).strip(),
    ])

    return players[0] + "|" + players[1]


def load_match_statuses():
    worksheet = get_worksheet()
    records = worksheet.get_all_records()

    statuses = {}

    for row in records:
        match_id = row.get("match_id")
        status = row.get("status", "seen")

        if match_id:
            statuses[match_id] = status

    return statuses


def add_new_matches(match_ids):
    if not match_ids:
        return

    worksheet = get_worksheet()
    existing_records = worksheet.get_all_records()

    existing_ids = {
        row.get("match_id")
        for row in existing_records
        if row.get("match_id")
    }

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []

    for match_id in match_ids:
        if match_id not in existing_ids:
            rows.append([match_id, now, "new"])

    if rows:
        worksheet.append_rows(rows)


def update_match_status(match_id, new_status):
    worksheet = get_worksheet()
    records = worksheet.get_all_records()

    for idx, row in enumerate(records, start=2):
        if row.get("match_id") == match_id:
            worksheet.update_cell(idx, 3, new_status)
            return

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    worksheet.append_row([match_id, now, new_status])


def status_label(status):
    if status == "new":
        return "🆕 NEW"
    if status == "wait":
        return "⏳ ČAKÁ NA KURZY"
    if status == "bet":
        return "🎯 STAVENÉ"
    if status == "seen":
        return "👁️ VIDENÉ"
    return status


def status_order(status):
    if status == "new":
        return 0
    if status == "wait":
        return 1
    if status == "bet":
        return 2
    if status == "seen":
        return 3
    return 9


def better_value(v1, v2, lower_is_better=False):
    if lower_is_better:
        if v1 < v2:
            return "p1"
        if v2 < v1:
            return "p2"
        return "tie"

    if v1 > v2:
        return "p1"
    if v2 > v1:
        return "p2"
    return "tie"


def player_line(player, value, rank=None, winner=False):
    mark = "🟢" if winner else "⚪"
    if rank is None:
        return f"{mark} **{player}:** {value}"
    return f"{mark} **{player}:** {value} `#{rank}`"


def surface_name(surface):
    if surface == "grass":
        return "Grass"
    if surface == "clay":
        return "Clay"
    if surface == "hard":
        return "Hard"
    return str(surface).capitalize()


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
    st.session_state["did_update"] = True


st.subheader("📊 Ranking vs Surface ELO mismatch")

try:
    df = pd.read_csv("ranking_vs_elo_mismatch.csv", sep=";")

    if df.empty:
        st.info("Žiadne ranking vs Surface ELO mismatch zápasy.")

    else:
        required_columns = [
            "Overall Elo 1",
            "Overall Elo 2",
            "Surface Elo 1",
            "Surface Elo 2",
            "Overall Elo Diff",
            "Surface Elo Diff",
            "Overall Elo Rank 1",
            "Overall Elo Rank 2",
            "Surface Elo Rank 1",
            "Surface Elo Rank 2",
        ]

        missing_columns = [
            col for col in required_columns if col not in df.columns
        ]

        if missing_columns:
            st.warning(
                "CSV ešte nemá nové ELO stĺpce. Spusti najprv 🔄 Aktualizovať všetko."
            )
            st.stop()

        date_options = sorted(df["DateLabel"].dropna().unique())
        tour_options = sorted(df["Tour"].dropna().unique())
        surface_options = sorted(df["Surface"].dropna().unique())

        selected_status = st.selectbox(
            "Zobraziť",
            ["Všetky", "Nové", "Čaká na kurzy", "Stavené", "Videné"]
        )

        selected_dates = st.multiselect(
            "Dni",
            date_options,
            default=date_options
        )

        selected_tours = st.multiselect(
            "Tour",
            tour_options,
            default=tour_options
        )

        selected_surfaces = st.multiselect(
            "Povrch",
            surface_options,
            default=surface_options
        )

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

        now_time = dt.now(ZoneInfo("Europe/Bratislava")).time()

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

        try:
            df_view["match_id"] = df_view.apply(make_match_id, axis=1)

            current_statuses = load_match_statuses()

            new_ids = [
                match_id
                for match_id in df_view["match_id"].tolist()
                if match_id not in current_statuses
            ]

            if st.session_state.get("did_update", False):
                add_new_matches(new_ids)

            current_statuses = load_match_statuses()

            df_view["Status"] = (
                df_view["match_id"]
                .map(current_statuses)
                .fillna("new")
            )

        except Exception as e:
            st.warning(f"Nepodarilo sa pripojiť ku Google Sheet: {repr(e)}")
            df_view["match_id"] = df_view.apply(make_match_id, axis=1)
            df_view["Status"] = "new"

        if selected_status == "Nové":
            df_view = df_view[df_view["Status"] == "new"]
        elif selected_status == "Čaká na kurzy":
            df_view = df_view[df_view["Status"] == "wait"]
        elif selected_status == "Stavené":
            df_view = df_view[df_view["Status"] == "bet"]
        elif selected_status == "Videné":
            df_view = df_view[df_view["Status"] == "seen"]

        df_view["StatusOrder"] = df_view["Status"].apply(status_order)

        df_view = df_view.sort_values(
            by=["StatusOrder", "DayOrder", "Time"],
            ascending=[True, True, True]
        )

        new_count = (df_view["Status"] == "new").sum()
        wait_count = (df_view["Status"] == "wait").sum()
        bet_count = (df_view["Status"] == "bet").sum()
        seen_count = (df_view["Status"] == "seen").sum()

        st.caption(
            f"Počet zápasov: {len(df_view)} | "
            f"Nové: {new_count} | "
            f"Čaká na kurzy: {wait_count} | "
            f"Stavené: {bet_count} | "
            f"Videné: {seen_count}"
        )

        for _, row in df_view.iterrows():
            status = row.get("Status", "new")
            badge = status_label(status)

            p1 = row["Player 1"]
            p2 = row["Player 2"]
            surface = row["Surface"]
            surface_title = surface_name(surface)

            ranking_fav = row["Ranking Favorite"]
            elo_fav = row["ELO Favorite"]

            rank_winner = better_value(
                row["Rank 1"],
                row["Rank 2"],
                lower_is_better=True
            )

            overall_winner = better_value(
                row["Overall Elo 1"],
                row["Overall Elo 2"]
            )

            surface_winner = better_value(
                row["Surface Elo 1"],
                row["Surface Elo 2"]
            )

            if elo_fav == p1:
                elo_text = f"🟦 Surface ELO → **{elo_fav}**"
            else:
                elo_text = f"🟧 Surface ELO → **{elo_fav}**"

            st.markdown(
                f"""
### {badge} · {row["DateLabel"]} · {row["Time"]}

🎾 **{p1}** vs **{p2}**

**Mismatch:** Ranking → **{ranking_fav}** | Surface ELO → **{elo_fav}**

⭐ **Ranking**  
{player_line(p1, "#" + str(row["Rank 1"]), winner=(rank_winner == "p1"))}  
{player_line(p2, "#" + str(row["Rank 2"]), winner=(rank_winner == "p2"))}  
Rozdiel: **{row["Rank Diff"]}**

🌍 **Overall ELO**  
{player_line(p1, row["Overall Elo 1"], row["Overall Elo Rank 1"], winner=(overall_winner == "p1"))}  
{player_line(p2, row["Overall Elo 2"], row["Overall Elo Rank 2"], winner=(overall_winner == "p2"))}  
Rozdiel: **{row["Overall Elo Diff"]}**

🌱 **{surface_title} ELO**  
{player_line(p1, row["Surface Elo 1"], row["Surface Elo Rank 1"], winner=(surface_winner == "p1"))}  
{player_line(p2, row["Surface Elo 2"], row["Surface Elo Rank 2"], winner=(surface_winner == "p2"))}  
Rozdiel: **{row["Surface Elo Diff"]}**

{elo_text}
"""
            )

            col_seen, col_wait, col_bet = st.columns(3)

            with col_seen:
                if st.button(
                    "👁️ Videné",
                    key=f"seen_{row['match_id']}"
                ):
                    update_match_status(row["match_id"], "seen")
                    st.rerun()

            with col_wait:
                if st.button(
                    "⏳ Čaká na kurzy",
                    key=f"wait_{row['match_id']}"
                ):
                    update_match_status(row["match_id"], "wait")
                    st.rerun()

            with col_bet:
                if st.button(
                    "🎯 Stavené",
                    key=f"bet_{row['match_id']}"
                ):
                    update_match_status(row["match_id"], "bet")
                    st.rerun()

            with st.expander("📊 Detail zápasu"):
                detail_df = pd.DataFrame(
                    {
                        p1: [
                            row["Rank 1"],
                            row["Overall Elo 1"],
                            row["Overall Elo Rank 1"],
                            row["Surface Elo 1"],
                            row["Surface Elo Rank 1"],
                        ],
                        p2: [
                            row["Rank 2"],
                            row["Overall Elo 2"],
                            row["Overall Elo Rank 2"],
                            row["Surface Elo 2"],
                            row["Surface Elo Rank 2"],
                        ],
                    },
                    index=[
                        "Ranking",
                        "Overall ELO",
                        "Overall ELO Rank",
                        f"{surface_title} ELO",
                        f"{surface_title} ELO Rank",
                    ]
                )

                st.dataframe(
                    detail_df,
                    use_container_width=True
                )

                st.markdown("---")
                st.write(f"Ranking favorit: {ranking_fav}")
                st.write(f"Surface ELO favorit: {elo_fav}")
                st.write(f"Rank rozdiel: {row['Rank Diff']}")
                st.write(f"Overall ELO rozdiel: {row['Overall Elo Diff']}")
                st.write(f"Surface ELO rozdiel: {row['Surface Elo Diff']}")
                st.write(f"Status: {status_label(status)}")

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
                by="Surface Elo Diff",
                ascending=False
            )

            st.dataframe(
                df_all,
                use_container_width=True,
                hide_index=True
            )

    except FileNotFoundError:
        st.info("Súbor flashscore_elo_matches.csv zatiaľ neexistuje.")