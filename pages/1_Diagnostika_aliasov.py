import os
import subprocess
import sys

import pandas as pd
import streamlit as st


PYTHON = sys.executable

st.set_page_config(
    page_title="Diagnostika aliasov",
    layout="wide",
)

st.title("🔎 Diagnostika aliasov")


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

    return result.stdout


def read_csv_if_exists(filename):
    if not os.path.exists(filename):
        return pd.DataFrame()

    try:
        return pd.read_csv(
            filename,
            sep=";",
        )
    except Exception as error:
        st.warning(
            f"Nepodarilo sa načítať {filename}: {error}"
        )
        return pd.DataFrame()


def only_current_days(df):
    if (
        not df.empty
        and "DateLabel" in df.columns
    ):
        return df[
            df["DateLabel"].isin(
                ["Today", "Day+1"]
            )
        ].copy()

    return df


if st.button(
    "🔄 Obnoviť diagnostiku",
    use_container_width=True,
):
    for script in [
        "diagnostics.py",
        "update_aliases.py",
    ]:
        if os.path.exists(script):
            st.write(f"Spúšťam: {script}")
            output = run_script(script)

            if output:
                st.code(output)

    st.success("Diagnostika bola obnovená.")
    st.rerun()


raw = only_current_days(
    read_csv_if_exists(
        "flashscore_matches.csv"
    )
)
shown = only_current_days(
    read_csv_if_exists(
        "flashscore_elo_matches.csv"
    )
)
skipped = only_current_days(
    read_csv_if_exists(
        "skipped_matches.csv"
    )
)
missing = read_csv_if_exists(
    "missing_players_summary.csv"
)
review = read_csv_if_exists(
    "review_aliases.csv"
)

raw_count = len(raw)
shown_count = len(shown)
skipped_count = len(skipped)

alias_skipped = 0
ranking_skipped = 0
elo_missing = 0

if (
    not skipped.empty
    and "Reason" in skipped.columns
):
    reasons = skipped["Reason"].astype(str)

    alias_skipped = int(
        reasons.str.contains(
            "not_in_aliases",
            case=False,
            na=False,
        ).sum()
    )

    ranking_skipped = int(
        reasons.str.contains(
            "not_in_rankings",
            case=False,
            na=False,
        ).sum()
    )

    elo_missing = int(
        reasons.str.contains(
            "elo",
            case=False,
            na=False,
        ).sum()
    )

columns = st.columns(6)

columns[0].metric(
    "Flashscore",
    raw_count,
)
columns[1].metric(
    "Zobrazené",
    shown_count,
)
columns[2].metric(
    "Vyradené",
    skipped_count,
)
columns[3].metric(
    "Chýba alias",
    alias_skipped,
)
columns[4].metric(
    "Mimo rankingu",
    ranking_skipped,
)
columns[5].metric(
    "Problém Elo",
    elo_missing,
)


st.subheader("Dôvody vyradenia")

if (
    skipped.empty
    or "Reason" not in skipped.columns
):
    st.info(
        "Nie sú dostupné údaje v skipped_matches.csv."
    )
else:
    reason_counts = (
        skipped["Reason"]
        .fillna("unknown")
        .value_counts()
        .rename_axis("Dôvod")
        .reset_index(name="Počet")
    )

    st.dataframe(
        reason_counts,
        use_container_width=True,
        hide_index=True,
    )


st.subheader("Chýbajúce mená")

if missing.empty:
    st.success(
        "Momentálne nie sú evidované žiadne "
        "chýbajúce mená."
    )
else:
    st.dataframe(
        missing,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "⬇️ Stiahnuť missing_players_summary.csv",
        data=missing.to_csv(
            sep=";",
            index=False,
        ).encode("utf-8-sig"),
        file_name="missing_players_summary.csv",
        mime="text/csv",
        use_container_width=True,
    )


st.subheader("Konkrétne vyradené zápasy")

if skipped.empty:
    st.info(
        "Nie sú dostupné vyradené zápasy."
    )
else:
    preferred_columns = [
        "DateLabel",
        "Time",
        "Tour",
        "Tournament",
        "Surface",
        "Player 1",
        "Player 2",
        "Reason",
        "Detail",
    ]

    visible_columns = [
        column
        for column in preferred_columns
        if column in skipped.columns
    ]

    st.dataframe(
        skipped[visible_columns]
        if visible_columns
        else skipped,
        use_container_width=True,
        hide_index=True,
    )


st.subheader("Návrhy aliasov")

if review.empty:
    st.info(
        "review_aliases.csv neobsahuje "
        "žiadnych kandidátov."
    )
else:
    st.dataframe(
        review,
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        "⬇️ Stiahnuť review_aliases.csv",
        data=review.to_csv(
            sep=";",
            index=False,
        ).encode("utf-8-sig"),
        file_name="review_aliases.csv",
        mime="text/csv",
        use_container_width=True,
    )


st.caption(
    "Doplnenie aliasov do manual_aliases.csv "
    "urob lokálne a následne súbor odošli na GitHub. "
    "Zmeny vykonané iba v Streamlit Cloude nemusia byť trvalé."
)
