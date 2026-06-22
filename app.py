import sys
import subprocess
from datetime import datetime

import streamlit as st
import pandas as pd

PYTHON = sys.executable

st.set_page_config(page_title="Tennis Surface ELO Finder", layout="wide")

st.title("🎾 Tennis Surface ELO Finder")

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


        now_time = datetime.now().time()

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

        st.caption(f"Počet zápasov: {len(df_view)}")

        for _, row in df_view.iterrows():
            st.markdown(
                f"""
### {row["DateLabel"]} · {row["Time"]}

**{row["Player 1"]}** vs **{row["Player 2"]}**

Ranking favorit: **{row["Ranking Favorite"]}**  
Rank rozdiel: **{row["Rank Diff"]}**

Surface ELO favorit: **{row["ELO Favorite"]}**  
ELO rozdiel: **{row["ELO Diff"]}**
"""
            )

            with st.expander("📊 Detail zápasu"):
                col_a, col_b = st.columns(2)

                with col_a:
                    st.markdown(f"#### {row['Player 1']}")
                    st.write(f"Rank: {row['Rank 1']}")
                    st.write(
                        f"Surface ELO Rank: {row['Surface Elo Rank 1']}"
                    )

                with col_b:
                    st.markdown(f"#### {row['Player 2']}")
                    st.write(f"Rank: {row['Rank 2']}")
                    st.write(
                        f"Surface ELO Rank: {row['Surface Elo Rank 2']}"
                    )

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