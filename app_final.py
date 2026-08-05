import os
import subprocess
import sys

from datetime import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from google_seen_matches import (
    add_saved_status,
    update_after_refresh,
)


PYTHON = sys.executable


st.set_page_config(
    page_title="Tenisové zápasy",
    layout="wide",
)

st.title("🎾 Tenisové zápasy")


def run_script(script):
    result = subprocess.run(
        [PYTHON, script],
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        st.error(f"Chyba v skripte: {script}")

        if result.stdout:
            st.code(result.stdout)

        if result.stderr:
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


def show_time(value):
    if pd.isna(value):
        return "LIVE"

    text = str(value).strip()

    if not text or text.lower() == "nan":
        return "LIVE"

    return text


def file_modified_text(filename):
    if not os.path.exists(filename):
        return "súbor neexistuje"

    modified = dt.fromtimestamp(
        os.path.getmtime(filename),
        tz=ZoneInfo("Europe/Bratislava"),
    )

    return modified.strftime("%d.%m.%Y %H:%M")


def load_current_matches():
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
        raise ValueError(
            "Vo výstupnom CSV chýbajú stĺpce: "
            + ", ".join(missing_columns)
        )

    # Aplikácia aj Google Sheets sledujú iba dnešné
    # a zajtrajšie zápasy.
    return df[
        df["DateLabel"].isin(
            [
                "Today",
                "Day+1",
            ]
        )
    ].copy()


def prepare_for_display(df):
    result = df.copy()

    result["MatchTime"] = pd.to_datetime(
        result["Time"],
        format="%H:%M",
        errors="coerce",
    )

    result["IsLive"] = result["MatchTime"].isna()

    # Poradie:
    # 0 = NOVÉ
    # 1 = LIVE, ale už videné
    # 2 = ostatné videné
    result["DisplayGroup"] = 2
    result.loc[
        result["IsLive"],
        "DisplayGroup",
    ] = 1
    result.loc[
        result["IsNew"],
        "DisplayGroup",
    ] = 0

    return result


def sort_matches(matches):
    return matches.sort_values(
        by=[
            "DisplayGroup",
            "MatchTime",
            "Tournament",
            "Player 1",
            "Player 2",
        ],
        ascending=[
            True,
            True,
            True,
            True,
            True,
        ],
        na_position="last",
    )


def render_matches(matches, empty_message):
    if matches.empty:
        st.info(empty_message)
        return

    for _, row in matches.iterrows():
        player_1 = row["Player 1"]
        player_2 = row["Player 2"]

        if bool(row["IsNew"]):
            status = "🟢 NOVÉ · "
        elif bool(row["IsLive"]):
            status = "🔴 LIVE · "
        else:
            status = ""

        time_text = show_time(
            row["Time"]
        )

        # Pri LIVE už stav obsahuje text LIVE, preto ho neopakujeme.
        if bool(row["IsLive"]):
            title = (
                f"{status}"
                f"{player_1} vs {player_2} · "
                f"{row['Tournament']}"
            )
        else:
            title = (
                f"{status}"
                f"{time_text} · "
                f"{player_1} vs {player_2} · "
                f"{row['Tournament']}"
            )

        with st.expander(
            title,
            expanded=False,
        ):
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


st.caption(
    "ATP Elo: "
    f"{file_modified_text('atp_elo.csv')} · "
    "WTA Elo: "
    f"{file_modified_text('wta_elo.csv')}"
)


col1, col2 = st.columns(2)


with col1:
    if st.button(
        "🎾 Aktualizovať zápasy",
        use_container_width=True,
    ):
        scripts = [
            "export_flashscore_matches.py",
            "flashscore_elo_compare.py",
        ]

        progress = st.progress(0)

        for index, script in enumerate(
            scripts,
            start=1,
        ):
            st.write(f"Spúšťam: {script}")
            run_script(script)
            progress.progress(
                index / len(scripts)
            )

        try:
            refreshed_df = (
                load_current_matches()
            )

            updated_df = update_after_refresh(
                refreshed_df
            )

            new_count = int(
                updated_df["IsNew"].sum()
            )

        except Exception as error:
            st.error(
                "Zápasy sa stiahli, ale nepodarilo "
                "sa aktualizovať stav NOVÉ v Google Sheets: "
                f"{error}"
            )
            st.stop()

        if new_count:
            st.success(
                f"Zápasy boli aktualizované. "
                f"Nové zápasy: {new_count}."
            )
        else:
            st.success(
                "Zápasy boli aktualizované. "
                "Žiadne nové zápasy."
            )

        st.rerun()


with col2:
    if st.button(
        "📈 Aktualizovať Elo",
        use_container_width=True,
    ):
        scripts = [
            "get_atp_elo_final.py",
            "get_wta_elo_final.py",
            "create_name_map.py",
            "flashscore_elo_compare.py",
        ]

        progress = st.progress(0)

        for index, script in enumerate(
            scripts,
            start=1,
        ):
            st.write(f"Spúšťam: {script}")
            run_script(script)
            progress.progress(
                index / len(scripts)
            )

        st.success(
            "Elo a porovnanie boli aktualizované."
        )
        st.rerun()


try:
    df = load_current_matches()

    # Pri obyčajnom otvorení alebo rerune iba načítame
    # uložený stav. Google Sheets sa nemení.
    df = add_saved_status(df)
    df = prepare_for_display(df)

    today = sort_matches(
        df[
            df["DateLabel"] == "Today"
        ].copy()
    )

    tomorrow = sort_matches(
        df[
            df["DateLabel"] == "Day+1"
        ].copy()
    )

    today_count = len(today)
    tomorrow_count = len(tomorrow)
    all_count = (
        today_count
        + tomorrow_count
    )

    today_new_count = int(
        today["IsNew"].sum()
    )
    tomorrow_new_count = int(
        tomorrow["IsNew"].sum()
    )
    total_new_count = (
        today_new_count
        + tomorrow_new_count
    )

    if total_new_count:
        st.success(
            f"🟢 Nové zápasy: {total_new_count} "
            f"(dnes {today_new_count}, "
            f"zajtra {tomorrow_new_count})"
        )

    view_labels = {
        f"🎾 Dnes ({today_count})": "today",
        f"🌅 Zajtra ({tomorrow_count})": "tomorrow",
        f"📋 Všetko ({all_count})": "all",
    }

    selected_label = st.radio(
        "Zobraziť zápasy",
        options=list(
            view_labels.keys()
        ),
        horizontal=True,
        label_visibility="collapsed",
    )

    selected_view = view_labels[
        selected_label
    ]

    if selected_view == "today":
        st.subheader(
            f"🎾 Dnešné zápasy ({today_count})"
        )
        render_matches(
            today,
            "Dnes nie sú k dispozícii "
            "žiadne zápasy s Elo dátami.",
        )

    elif selected_view == "tomorrow":
        st.subheader(
            f"🌅 Zajtrajšie zápasy "
            f"({tomorrow_count})"
        )
        render_matches(
            tomorrow,
            "Na zajtra nie sú k dispozícii "
            "žiadne zápasy s Elo dátami.",
        )

    else:
        st.subheader(
            f"🎾 Dnešné zápasy ({today_count})"
        )
        render_matches(
            today,
            "Dnes nie sú k dispozícii "
            "žiadne zápasy s Elo dátami.",
        )

        st.divider()

        st.subheader(
            f"🌅 Zajtrajšie zápasy "
            f"({tomorrow_count})"
        )
        render_matches(
            tomorrow,
            "Na zajtra nie sú k dispozícii "
            "žiadne zápasy s Elo dátami.",
        )

except FileNotFoundError as error:
    st.info(
        "Potrebný súbor neexistuje: "
        f"{error}. Klikni na "
        "🎾 Aktualizovať zápasy."
    )

except Exception as error:
    st.error(
        f"Chyba pri načítaní dát: {error}"
    )
