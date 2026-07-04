import sys

import subprocess

from datetime import datetime as dt

from zoneinfo import ZoneInfo

import pandas as pd

import streamlit as st

PYTHON = sys.executable

st.set_page_config(page_title="Dnešné zápasy", layout="wide")

st.title("🎾 Dnešné zápasy – ešte nezačaté")

def run_script(script):

    result = subprocess.run([PYTHON, script], text=True, capture_output=True)

    if result.returncode != 0:

        st.error(result.stderr)

        st.stop()

    lines = []

    for line in result.stdout.splitlines():

        if (

            line.startswith("Hotovo")

            or line.startswith("Zápasov:")

            or line.startswith("Výstup:")

            or line.startswith("Súbor:")

        ):

            lines.append(line)

    if lines:

        st.text("\n".join(lines))

def show(v):

    if pd.isna(v) or v == "":

        return "—"

    return v

if st.button("🔄 Aktualizovať dáta"):

    for script in [

        "export_flashscore_matches.py",

        "flashscore_elo_compare.py",

    ]:

        st.write(f"Spúšťam: {script}")

        run_script(script)

    st.success("Aktualizované.")

try:

    df = pd.read_csv("flashscore_elo_matches.csv", sep=";")
    
    st.write("Počet riadkov v CSV:", len(df))
    st.write(df["DateLabel"].value_counts())

    now_time = dt.now(ZoneInfo("Europe/Bratislava")).time()

    df["MatchTime"] = pd.to_datetime(

        df["Time"],

        format="%H:%M",

        errors="coerce"

    ).dt.time

    df = df[

        (df["DateLabel"] == "Today")

        & (df["MatchTime"] >= now_time)

    ].copy()

    df = df.sort_values(["Time", "Tournament"])

    st.caption(f"Počet zápasov: {len(df)}")

    for _, row in df.iterrows():

        p1 = row["Player 1"]

        p2 = row["Player 2"]

        title = f"{row['Time']} · {p1} vs {p2} · {row['Tournament']}"

        with st.expander(title, expanded=False):

            st.write(f"{row['Tour']} · {row['Surface']}")

            table = pd.DataFrame(

                {

                    p1: [

                        show(row.get("Rank 1")),

                        show(row.get("Overall Elo 1")),

                        show(row.get("Overall Elo Rank 1")),

                        show(row.get("Surface Elo 1")),

                        show(row.get("Surface Elo Rank 1")),

                    ],

                    p2: [

                        show(row.get("Rank 2")),

                        show(row.get("Overall Elo 2")),

                        show(row.get("Overall Elo Rank 2")),

                        show(row.get("Surface Elo 2")),

                        show(row.get("Surface Elo Rank 2")),

                    ],

                },

                index=[

                    "Rank",

                    "Elo",

                    "Elo Rank",

                    "Surface Elo",

                    "Surface Elo Rank",

                ]

            )

            st.dataframe(table, use_container_width=True)

except FileNotFoundError:

    st.info("Najprv klikni na 🔄 Aktualizovať dáta.")
