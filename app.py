import pandas as pd
import streamlit as st
from datetime import datetime as dt
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Dnešné zápasy", layout="wide")
st.title("🎾 Dnešné zápasy – ešte nezačaté")

def show(v):
    if pd.isna(v) or v == "":
        return "—"
    return v

try:
    df = pd.read_csv("flashscore_elo_matches.csv", sep=";")

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

        with st.expander(
            f"{row['Time']} · {p1} vs {p2} · {row['Tournament']}",
            expanded=False
        ):
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
                    "ATP/WTA Rank",
                    "Elo",
                    "Elo Rank",
                    "Surface Elo",
                    "Surface Elo Rank",
                ]
            )

            st.dataframe(table, use_container_width=True)

except FileNotFoundError:
    st.info("Najprv musí existovať flashscore_elo_matches.csv.")
