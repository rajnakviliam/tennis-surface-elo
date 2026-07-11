import sys
import subprocess
from datetime import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st


PYTHON = sys.executable

st.set_page_config(
    page_title="Dnešné zápasy",
    layout="wide",
)

st.title("🎾 Dnešné zápasy – ešte nezačaté")


def run_script(script):
    result = subprocess.run(
        [PYTHON, script],
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        st.error(f"Chyba v {script}")
        st.code(result.stderr)
        st.stop()

    lines = []

    for line in result.stdout.splitlines():
        line = line.strip()

        if (
            line.startswith("Hotovo")
            or line.startswith("Zápasov:")
            or line.startswith("Výstup:")
            or line.startswith("Súbor:")
            or line.startswith("Počet")
        ):
            lines.append(line)

    if lines:
        st.text("\n".join(lines))


def show(value):
    if pd.isna(value) or value == "":
        return "—"

    try:
        number = float(value)

        if number.is_integer():
            return int(number)

        return round(number, 1)

    except (TypeError, ValueError):
        return value


if st.button("🔄 Aktualizovať dáta", use_container_width=True):
    scripts = [
        "export_flashscore_matches.py",
        "get_atp_elo_final.py",
        "get_wta_elo_final.py",
        "create_name_map.py",
        "flashscore_elo_compare.py",
    ]

    progress = st.progress(0)

    for index, script in enumerate(scripts, start=1):
        st.write(f"Spúšťam: {script}")
        run_script(script)
        progress.progress(index / len(scripts))

    st.success("Zápasy, rankingy a Elo boli aktualizované.")
    st.rerun()


try:
    df = pd.read_csv(
        "flashscore_elo_matches.csv",
        sep=";",
    )

    required_columns = [
        "DateLabel",
        "Time",
        "Tournament",
        "Tour",
        "Surface",
        "Player 1",
        "Player 2",
        "Rank 1",
        "Rank 2",
        "Overall Elo 1",
        "Overall Elo 2",
        "Overall Elo Rank 1",
        "Overall Elo Rank 2",
        "Surface Elo 1",
        "Surface Elo 2",
        "Surface Elo Rank 1",
        "Surface Elo Rank 2",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        st.error(
            "Vo výstupnom CSV chýbajú stĺpce: "
            + ", ".join(missing_columns)
        )
        st.stop()

    now_time = dt.now(
        ZoneInfo("Europe/Bratislava")
    ).time()

    df["MatchTime"] = pd.to_datetime(
        df["Time"],
        format="%H:%M",
        errors="coerce",
    ).dt.time

    df = df[
        (df["DateLabel"] == "Today")
        & df["MatchTime"].notna()
        & (df["MatchTime"] >= now_time)
    ].copy()

    df = df.sort_values(
        by=["Time", "Tournament"],
        ascending=[True, True],
    )

    st.caption(f"Ešte nezačaté zápasy: {len(df)}")

    for _, row in df.iterrows():
        player_1 = row["Player 1"]
        player_2 = row["Player 2"]

        title = (
            f"{row['Time']} · "
            f"{player_1} vs {player_2} · "
            f"{row['Tournament']}"
        )

        with st.expander(title, expanded=False):
            st.caption(
                f"{row['Tour']} · {row['Surface']}"
            )

            table = pd.DataFrame(
                {
                    player_1: [
                        show(row["Rank 1"]),
                        show(row["Overall Elo 1"]),
                        show(row["Overall Elo Rank 1"]),
                        show(row["Surface Elo 1"]),
                        show(row["Surface Elo Rank 1"]),
                    ],
                    player_2: [
                        show(row["Rank 2"]),
                        show(row["Overall Elo 2"]),
                        show(row["Overall Elo Rank 2"]),
                        show(row["Surface Elo 2"]),
                        show(row["Surface Elo Rank 2"]),
                    ],
                },
                index=[
                    "ATP/WTA Rank",
                    "Overall Elo",
                    "Overall Elo Rank",
                    "Surface Elo",
                    "Surface Elo Rank",
                ],
            )

            st.dataframe(
                table,
                use_container_width=True,
            )

except FileNotFoundError:
    st.info("Najprv klikni na 🔄 Aktualizovať dáta.")

except Exception as error:
    st.error(f"Chyba pri načítaní dát: {error}")
