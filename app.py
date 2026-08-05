import os
import subprocess
import sys

from datetime import datetime as dt
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from google_seen_matches import (
    add_saved_status,
    set_pinned,
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

    return df[
        df["DateLabel"].isin(
            [
                "Today",
                "Day+1",
            ]
        )
    ].copy()


def load_current_rows(filename):
    """
    Načíta iba riadky Today a Day+1.

    Názvy stĺpcov aj hodnoty DateLabel sa očistia od
    medzier a prípadného BOM znaku.
    """
    if not os.path.exists(filename):
        return pd.DataFrame()

    try:
        data = pd.read_csv(
            filename,
            sep=";",
        )
    except Exception:
        return pd.DataFrame()

    data.columns = [
        str(column)
        .replace("\ufeff", "")
        .strip()
        for column in data.columns
    ]

    if "DateLabel" in data.columns:
        date_labels = (
            data["DateLabel"]
            .astype(str)
            .str.strip()
        )

        data = data[
            date_labels.isin(
                ["Today", "Day+1"]
            )
        ].copy()

    return data


def get_match_counts():
    """
    Počty vychádzajú z výstupov porovnávacieho skriptu:

    - zobrazené = flashscore_elo_matches.csv
    - vyradené = skipped_matches.csv
    - Flashscore dvojhry = zobrazené + vyradené
    - chýba alias = vyradené s dôvodom not_in_aliases
    """
    shown = load_current_rows(
        "flashscore_elo_matches.csv"
    )
    skipped = load_current_rows(
        "skipped_matches.csv"
    )

    shown_count = len(shown)
    skipped_count = len(skipped)
    flashscore_count = (
        shown_count
        + skipped_count
    )

    alias_skip_count = 0

    if (
        not skipped.empty
        and "Reason" in skipped.columns
    ):
        alias_skip_count = int(
            skipped["Reason"]
            .astype(str)
            .str.contains(
                "not_in_aliases",
                case=False,
                na=False,
            )
            .sum()
        )

    return (
        flashscore_count,
        shown_count,
        skipped_count,
        alias_skip_count,
    )


def count_alias_skips():
    return get_match_counts()[3]


def prepare_for_display(df):
    result = df.copy()

    result["MatchTime"] = pd.to_datetime(
        result["Time"],
        format="%H:%M",
        errors="coerce",
    )
    result["IsLive"] = result["MatchTime"].isna()

    # Pripnutý zápas sa nezobrazuje zároveň ako NOVÝ.
    result.loc[
        result["IsPinned"],
        "IsNew",
    ] = False

    # Poradie:
    # 0 = pripnuté
    # 1 = nové
    # 2 = live, ale už videné
    # 3 = ostatné
    result["DisplayGroup"] = 3
    result.loc[
        result["IsLive"],
        "DisplayGroup",
    ] = 2
    result.loc[
        result["IsNew"],
        "DisplayGroup",
    ] = 1
    result.loc[
        result["IsPinned"],
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

        if bool(row["IsPinned"]):
            status = "📌 "
        elif bool(row["IsNew"]):
            status = "🟢 NOVÉ · "
        elif bool(row["IsLive"]):
            status = "🔴 LIVE · "
        else:
            status = ""

        if bool(row["IsLive"]):
            title = (
                f"{status}"
                f"{player_1} vs {player_2} · "
                f"{row['Tournament']}"
            )
        else:
            title = (
                f"{status}"
                f"{show_time(row['Time'])} · "
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

            pinned = bool(row["IsPinned"])
            button_text = (
                "📌 Odopnúť zápas"
                if pinned
                else "📌 Pripnúť zápas"
            )

            if st.button(
                button_text,
                key=f"pin_{row['MatchID']}",
                use_container_width=True,
            ):
                try:
                    set_pinned(
                        row["MatchID"],
                        not pinned,
                    )
                except Exception as error:
                    st.error(
                        "Nepodarilo sa zmeniť pripnutie: "
                        f"{error}"
                    )
                    st.stop()

                st.rerun()


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
            updated_df = update_after_refresh(
                load_current_matches()
            )
            new_count = int(
                updated_df["IsNew"].sum()
            )
        except Exception as error:
            st.error(
                "Zápasy sa stiahli, ale nepodarilo "
                "sa aktualizovať stav v Google Sheets: "
                f"{error}"
            )
            st.stop()

        alias_skip_count = (
            count_alias_skips()
        )

        message_parts = [
            "Zápasy boli aktualizované.",
            (
                f"Nové zápasy: {new_count}."
                if new_count
                else "Žiadne nové zápasy."
            ),
        ]

        if alias_skip_count:
            message_parts.append(
                f"Chýba alias pri "
                f"{alias_skip_count} zápasoch."
            )

        st.success(
            " ".join(message_parts)
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


(
    raw_count,
    shown_count,
    skipped_count,
    alias_skip_count,
) = get_match_counts()

st.markdown(
    (
        "<div style='display:flex;gap:8px;"
        "flex-wrap:wrap;margin:0.35rem 0 0.8rem 0;'>"
        f"<div style='flex:1;min-width:92px;padding:8px 10px;"
        "border:1px solid rgba(128,128,128,.28);"
        "border-radius:10px;text-align:center;'>"
        "<div style='font-size:.78rem;opacity:.72;'>🎾 Flashscore dvojhry</div>"
        f"<div style='font-size:1.35rem;font-weight:700;'>{raw_count}</div></div>"
        f"<div style='flex:1;min-width:92px;padding:8px 10px;"
        "border:1px solid rgba(128,128,128,.28);"
        "border-radius:10px;text-align:center;'>"
        "<div style='font-size:.78rem;opacity:.72;'>✅ Zobrazené</div>"
        f"<div style='font-size:1.35rem;font-weight:700;'>{shown_count}</div></div>"
        f"<div style='flex:1;min-width:92px;padding:8px 10px;"
        "border:1px solid rgba(128,128,128,.28);"
        "border-radius:10px;text-align:center;'>"
        "<div style='font-size:.78rem;opacity:.72;'>⚠️ Chýba alias</div>"
        f"<div style='font-size:1.35rem;font-weight:700;'>{alias_skip_count}</div></div>"
        "</div>"
    ),
    unsafe_allow_html=True,
)

if alias_skip_count:
    st.warning(
        f"Chýba alias pri "
        f"{alias_skip_count} dnešných alebo "
        "zajtrajších dvojhrách. "
        "Podrobnosti sú na stránke "
        "Diagnostika aliasov."
    )
elif raw_count:
    st.caption(
        "✅ Pri dnešných a zajtrajších "
        "dvojhrách nechýba žiadny alias."
    )


try:
    df = load_current_matches()
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
    all_count = today_count + tomorrow_count

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

    pinned_count = int(
        df["IsPinned"].sum()
    )

    messages = []
    if pinned_count:
        messages.append(
            f"📌 Pripnuté: {pinned_count}"
        )
    if total_new_count:
        messages.append(
            f"🟢 Nové: {total_new_count} "
            f"(dnes {today_new_count}, "
            f"zajtra {tomorrow_new_count})"
        )

    if messages:
        st.success(" · ".join(messages))

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
