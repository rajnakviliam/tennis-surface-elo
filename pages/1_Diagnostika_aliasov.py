import os
import subprocess
import sys

import pandas as pd
import streamlit as st

from github_persistence import persist_file_to_github


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
        df = pd.read_csv(filename, sep=";")
        df.columns = [
            str(column).replace("\ufeff", "").strip()
            for column in df.columns
        ]
        return df
    except Exception as error:
        st.warning(
            f"Nepodarilo sa načítať {filename}: {error}"
        )
        return pd.DataFrame()


def only_current_days(df):
    if not df.empty and "DateLabel" in df.columns:
        labels = df["DateLabel"].astype(str).str.strip()
        return df[
            labels.isin(["Today", "Day+1"])
        ].copy()

    return df


def clean(value):
    if pd.isna(value):
        return ""

    return " ".join(
        str(value or "").replace("\xa0", " ").split()
    ).strip()


def detect_alias_columns(df):
    lower = {
        str(column).strip().casefold(): column
        for column in df.columns
    }

    alias_candidates = [
        "alias",
        "flashscore",
        "flashscore_name",
        "source_name",
    ]
    player_candidates = [
        "player",
        "canonical",
        "canonical_name",
        "ta_name",
        "tennisabstract",
        "tennis_abstract",
    ]

    alias_col = next(
        (
            lower[name]
            for name in alias_candidates
            if name in lower
        ),
        None,
    )
    player_col = next(
        (
            lower[name]
            for name in player_candidates
            if name in lower
        ),
        None,
    )
    tour_col = lower.get("tour")

    if alias_col is None and len(df.columns) >= 1:
        alias_col = df.columns[0]

    if player_col is None and len(df.columns) >= 2:
        player_col = df.columns[1]

    return alias_col, player_col, tour_col


def append_alias_to_file(
    filename,
    alias,
    player,
    tour,
):
    alias = clean(alias)
    player = clean(player)
    tour = clean(tour)

    df = read_csv_if_exists(filename)

    if df.empty and not os.path.exists(filename):
        df = pd.DataFrame(
            columns=["Alias", "Player", "Tour"]
        )

    if len(df.columns) < 2:
        raise ValueError(
            f"{filename} nemá použiteľnú schému aliasov."
        )

    alias_col, player_col, tour_col = (
        detect_alias_columns(df)
    )

    if alias_col is None or player_col is None:
        raise ValueError(
            f"V {filename} neviem určiť stĺpce Alias a Player."
        )

    normalized_alias = alias.casefold()

    if not df.empty:
        same_alias = (
            df[alias_col]
            .astype(str)
            .map(clean)
            .str.casefold()
            == normalized_alias
        )

        if same_alias.any():
            existing_players = (
                df.loc[same_alias, player_col]
                .astype(str)
                .map(clean)
                .unique()
                .tolist()
            )

            if player in existing_players:
                return False, "Alias už existuje."

            return (
                False,
                "Alias už existuje pre iného hráča: "
                + ", ".join(existing_players),
            )

    new_row = {
        column: ""
        for column in df.columns
    }
    new_row[alias_col] = alias
    new_row[player_col] = player

    if tour_col is not None:
        new_row[tour_col] = tour

    df = pd.concat(
        [df, pd.DataFrame([new_row])],
        ignore_index=True,
    )

    df.to_csv(
        filename,
        sep=";",
        index=False,
        encoding="utf-8-sig",
    )

    return True, "Alias bol pridaný."

def apply_manual_aliases_to_runtime():
    manual = read_csv_if_exists(
        "manual_aliases.csv"
    )

    if manual.empty:
        return 0

    alias_col, player_col, tour_col = (
        detect_alias_columns(manual)
    )

    if alias_col is None or player_col is None:
        return 0

    added = 0

    for _, row in manual.iterrows():
        alias = clean(
            row.get(alias_col, "")
        )
        player = clean(
            row.get(player_col, "")
        )

        tour = (
            clean(row.get(tour_col, ""))
            if tour_col is not None
            else ""
        )

        if not alias or not player:
            continue

        was_added, _ = append_alias_to_file(
            "aliases.csv",
            alias,
            player,
            tour,
        )

        if was_added:
            added += 1

    return added

def apply_generated_safe_aliases():
    generated = read_csv_if_exists(
        "flashscore_generated_aliases.csv"
    )
    aliases = read_csv_if_exists("aliases.csv")

    if generated.empty or aliases.empty:
        return 0, 0

    g_alias, g_player, g_tour = (
        detect_alias_columns(generated)
    )
    a_alias, a_player, a_tour = (
        detect_alias_columns(aliases)
    )

    if (
        g_alias is None
        or g_player is None
        or a_alias is None
        or a_player is None
    ):
        return 0, 0

    existing = {}

    for _, row in aliases.iterrows():
        key = clean(row[a_alias]).casefold()
        if not key:
            continue
        existing.setdefault(key, set()).add(
            clean(row[a_player])
        )

    rows_to_add = []
    skipped_collision = 0

    for _, row in generated.iterrows():
        alias = clean(row[g_alias])
        player = clean(row[g_player])
        tour = (
            clean(row[g_tour])
            if g_tour is not None
            else ""
        )

        if not alias or not player:
            continue

        key = alias.casefold()

        if key in existing:
            if player not in existing[key]:
                skipped_collision += 1
            continue

        new_row = {
            column: ""
            for column in aliases.columns
        }
        new_row[a_alias] = alias
        new_row[a_player] = player

        if a_tour is not None:
            new_row[a_tour] = tour

        rows_to_add.append(new_row)
        existing[key] = {player}

    if rows_to_add:
        aliases = pd.concat(
            [aliases, pd.DataFrame(rows_to_add)],
            ignore_index=True,
        )

        aliases.to_csv(
            "aliases.csv",
            sep=";",
            index=False,
            encoding="utf-8-sig",
        )

    return len(rows_to_add), skipped_collision


def refresh_alias_pipeline():
    manual_added = apply_manual_aliases_to_runtime()

    if manual_added:
        st.write(
            f"Ručných aliasov obnovených do runtime: "
            f"{manual_added}"
        )
    for script in [
        "generate_flashscore_aliases.py",
        "audit_generated_flashscore_aliases.py",
        "propose_alias_candidates.py",
    ]:
        if os.path.exists(script):
            st.write(f"Spúšťam: {script}")
            output = run_script(script)

            if output:
                st.code(output)

    added, collisions = (
        apply_generated_safe_aliases()
    )

    if added:
        st.write(
            f"Automaticky pridaných bezpečných "
            f"aliasov do runtime: {added}"
        )

    if collisions:
        st.warning(
            f"{collisions} generovaných aliasov sa "
            "nepridalo pre kolíziu."
        )

    if os.path.exists(
        "flashscore_elo_compare.py"
    ):
        st.write(
            "Spúšťam: flashscore_elo_compare.py"
        )
        run_script(
            "flashscore_elo_compare.py"
        )

    for script in [
        "audit_generated_flashscore_aliases.py",
        "propose_alias_candidates.py",
    ]:
        if os.path.exists(script):
            st.write(f"Spúšťam znova: {script}")
            run_script(script)


if st.button(
    "🔄 Obnoviť diagnostiku aliasov",
    use_container_width=True,
):
    refresh_alias_pipeline()
    st.success(
        "Diagnostika aliasov bola obnovená "
        "nad aktuálnymi zápasmi."
    )
    st.rerun()


raw = only_current_days(
    read_csv_if_exists("flashscore_matches.csv")
)
shown = only_current_days(
    read_csv_if_exists("flashscore_elo_matches.csv")
)
skipped = only_current_days(
    read_csv_if_exists("skipped_matches.csv")
)
missing = read_csv_if_exists(
    "missing_players_summary.csv"
)
review = read_csv_if_exists(
    "review_aliases.csv"
)
candidates = read_csv_if_exists(
    "flashscore_alias_review_candidates.csv"
)
players_master = read_csv_if_exists(
    "players_master.csv"
)
not_in_ta = read_csv_if_exists(
    "not_in_tennis_abstract.csv"
)


def find_match_context(flash_name, tour, raw_matches):
    if raw_matches.empty:
        return []

    contexts = []

    for _, match in raw_matches.iterrows():
        match_tour = clean(match.get("Tour", ""))

        if tour and match_tour and tour.casefold() != match_tour.casefold():
            continue

        player_1 = clean(match.get("Player 1", ""))
        player_2 = clean(match.get("Player 2", ""))

        if (
            player_1.casefold() != flash_name.casefold()
            and player_2.casefold() != flash_name.casefold()
        ):
            continue

        date_label = clean(match.get("DateLabel", ""))
        tournament = clean(match.get("Tournament", ""))

        if date_label == "Today":
            date_text = "Dnes"
        elif date_label == "Day+1":
            date_text = "Zajtra"
        else:
            date_text = date_label or "—"

        contexts.append(
            {
                "Date": date_text,
                "Tournament": tournament or "—",
            }
        )

    unique_contexts = []
    seen = set()

    for context in contexts:
        key = (
            context["Date"],
            context["Tournament"],
        )

        if key in seen:
            continue

        seen.add(key)
        unique_contexts.append(context)

    return unique_contexts

def player_choices_for_tour(tour):
    if players_master.empty:
        return []

    if "Player" not in players_master.columns:
        return []

    pool = players_master.copy()

    if "Tour" in pool.columns and tour:
        pool = pool[
            pool["Tour"]
            .astype(str)
            .str.strip()
            .str.casefold()
            == tour.casefold()
        ]

    choices = (
        pool["Player"]
        .astype(str)
        .map(clean)
    )

    choices = [
        name
        for name in choices
        if name
    ]

    return sorted(
        set(choices),
        key=str.casefold,
    )


def mark_not_in_tennis_abstract(
    flash_name,
    tour,
):
    filename = "not_in_tennis_abstract.csv"

    df = read_csv_if_exists(filename)

    if df.empty and not os.path.exists(filename):
        df = pd.DataFrame(
            columns=[
                "FlashscoreName",
                "Tour",
            ]
        )

    if "FlashscoreName" not in df.columns:
        df["FlashscoreName"] = ""

    if "Tour" not in df.columns:
        df["Tour"] = ""

    same = (
        df["FlashscoreName"]
        .astype(str)
        .map(clean)
        .str.casefold()
        == flash_name.casefold()
    ) & (
        df["Tour"]
        .astype(str)
        .map(clean)
        .str.casefold()
        == tour.casefold()
    )

    if not same.any():
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "FlashscoreName": flash_name,
                            "Tour": tour,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

        df.to_csv(
            filename,
            sep=";",
            index=False,
            encoding="utf-8-sig",
        )


def already_marked_not_in_ta(
    flash_name,
    tour,
):
    if not_in_ta.empty:
        return False

    if "FlashscoreName" not in not_in_ta.columns:
        return False

    tour_series = (
        not_in_ta["Tour"]
        if "Tour" in not_in_ta.columns
        else pd.Series(
            [""] * len(not_in_ta),
            index=not_in_ta.index,
        )
    )

    same_name = (
        not_in_ta["FlashscoreName"]
        .astype(str)
        .map(clean)
        .str.casefold()
        == flash_name.casefold()
    )

    same_tour = (
        tour_series
        .astype(str)
        .map(clean)
        .str.casefold()
        == tour.casefold()
    )

    return bool(
        (same_name & same_tour).any()
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

columns[0].metric("Flashscore", raw_count)
columns[1].metric("Zobrazené", shown_count)
columns[2].metric("Vyradené", skipped_count)
columns[3].metric("Chýba alias", alias_skipped)
columns[4].metric("Mimo rankingu", ranking_skipped)
columns[5].metric("Problém Elo", elo_missing)


st.subheader("✅ Schválenie navrhnutých aliasov")

if candidates.empty:
    st.info(
        "Nie sú dostupní kandidáti na ručné "
        "schválenie. Klikni na Obnoviť diagnostiku."
    )
else:
    candidates = candidates.copy()

    for _, row in candidates.iterrows():
        flash_name = clean(
            row.get("FlashscoreName", "")
        )
        tour = clean(
            row.get("Tour", "")
        )

        if not flash_name:
            continue

        if already_marked_not_in_ta(
            flash_name,
            tour,
        ):
            continue

        options = []

        for number in [1, 2, 3]:
            candidate = clean(
                row.get(
                    f"Candidate{number}",
                    "",
                )
            )

            if not candidate:
                continue

            score = clean(
                row.get(
                    f"Score{number}",
                    "",
                )
            )
            reason = clean(
                row.get(
                    f"Reason{number}",
                    "",
                )
            )

            label = candidate

            if score:
                label += f" · skóre {score}"

            if reason:
                label += f" · {reason}"

            options.append(
                (
                    candidate,
                    label,
                )
            )

        icon = "⚠️" if options else "❓"

        with st.expander(
            f"{icon} {flash_name} · {tour}",
            expanded=False,
        ):
            contexts = find_match_context(
                flash_name,
                tour,
                raw,
            )

            for context in contexts:
                st.caption(
                    f"📅 {context['Date']} · "
                    f"🏆 {context['Tournament']}"
                )

            selected_player = None

            if options:
                st.write(
                    "Navrhnutí kandidáti"
                )

                labels = [
                    label
                    for _, label in options
                ]

                selected_label = st.radio(
                    "Vyber kandidáta",
                    options=labels,
                    key=(
                        f"candidate_"
                        f"{tour}_{flash_name}"
                    ),
                    label_visibility="collapsed",
                )

                selected_player = next(
                    player
                    for player, label in options
                    if label == selected_label
                )
            else:
                st.info(
                    "Automaticky sa nenašiel "
                    "vhodný kandidát."
                )

            manual_key = (
                f"manual_picker_"
                f"{tour}_{flash_name}"
            )

            if manual_key not in st.session_state:
                st.session_state[
                    manual_key
                ] = False

            if st.button(
                "🔍 Vybrať iného hráča",
                key=(
                    f"open_manual_"
                    f"{tour}_{flash_name}"
                ),
                use_container_width=True,
            ):
                st.session_state[
                    manual_key
                ] = not st.session_state[
                    manual_key
                ]

            if st.session_state[
                manual_key
            ]:
                manual_choices = (
                    player_choices_for_tour(
                        tour
                    )
                )

                if manual_choices:
                    search_text = st.text_input(
                        f"Napíš časť mena ({tour})",
                        key=(
                            f"manual_search_"
                            f"{tour}_{flash_name}"
                        ),
                        placeholder=(
                            "napr. Huertas, Arklon, Tsitsipas..."
                        ),
                    )

                    filtered_choices = manual_choices

                    if search_text:
                        needle = clean(
                            search_text
                        ).casefold()

                        filtered_choices = [
                            name
                            for name in manual_choices
                            if needle in name.casefold()
                        ]

                    if not search_text:
                        st.caption(
                            "Napíš aspoň časť mena "
                            "a zoznam sa zúži."
                        )
                    elif not filtered_choices:
                        st.warning(
                            "Nenašiel sa žiadny hráč "
                            "s týmto textom."
                        )
                    else:
                        st.caption(
                            f"Nájdených: "
                            f"{len(filtered_choices)}"
                        )

                        manual_selected = st.selectbox(
                            "Vyber hráča",
                            options=filtered_choices,
                            key=(
                                f"manual_select_"
                                f"{tour}_{flash_name}"
                            ),
                        )

                        if manual_selected:
                            selected_player = (
                                manual_selected
                            )
                else:
                    st.warning(
                        "V players_master.csv "
                        "nie sú dostupní hráči "
                        f"pre {tour}."
                    )

            if selected_player:
                if st.button(
                    (
                        "✅ Potvrdiť: "
                        f"{selected_player}"
                    ),
                    key=(
                        f"approve_"
                        f"{tour}_{flash_name}"
                    ),
                    use_container_width=True,
                ):
                    try:
                        manual_added, manual_msg = (
                            append_alias_to_file(
                                "manual_aliases.csv",
                                flash_name,
                                selected_player,
                                tour,
                            )
                        )

                        if manual_added:
                            github_ok, github_msg = persist_file_to_github(
                                "manual_aliases.csv",
                                repo_path="manual_aliases.csv",
                                commit_message=(
                                    f"Add alias: {flash_name} -> {selected_player}"
                                ),
                            )

                            if github_ok:
                                st.success(github_msg)
                            else:
                                st.warning(github_msg)

                        runtime_added, runtime_msg = (
                            append_alias_to_file(
                                "aliases.csv",
                                flash_name,
                                selected_player,
                                tour,
                            )
                        )

                        if os.path.exists(
                            "flashscore_elo_compare.py"
                        ):
                            run_script(
                                "flashscore_elo_compare.py"
                            )

                        for script in [
                            "audit_generated_flashscore_aliases.py",
                            "propose_alias_candidates.py",
                        ]:
                            if os.path.exists(script):
                                run_script(script)

                        if manual_added or runtime_added:
                            st.success(
                                f"{flash_name} → "
                                f"{selected_player}"
                            )
                        else:
                            st.info(
                                manual_msg
                                + " "
                                + runtime_msg
                            )

                        st.rerun()

                    except Exception as error:
                        st.error(
                            "Alias sa nepodarilo uložiť: "
                            f"{error}"
                        )

            if st.button(
                "🚫 Hráč nie je v Tennis Abstract",
                key=(
                    f"not_in_ta_"
                    f"{tour}_{flash_name}"
                ),
                use_container_width=True,
            ):
                mark_not_in_tennis_abstract(
                    flash_name,
                    tour,
                )

                github_ok, github_msg = persist_file_to_github(
                    "not_in_tennis_abstract.csv",
                    repo_path="not_in_tennis_abstract.csv",
                    commit_message=(
                        f"Mark not in Tennis Abstract: "
                        f"{flash_name} ({tour})"
                    ),
                )
                
                if github_ok:
                    st.success(github_msg)
                else:
                    st.warning(github_msg)

                st.success(
                    f"{flash_name} bol označený "
                    "ako nenájdený v Tennis Abstract."
                )

                st.rerun()


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


st.subheader("Pôvodné návrhy aliasov")

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
    "Potvrdené aliasy sa zapíšu do manual_aliases.csv aj aliases.csv "
    "a aplikácia sa zároveň pokúsi uložiť manual_aliases.csv do GitHubu. "
    "Ak GitHub token nie je nastavený, zmena zostane iba v runtime. "
    "Označenie „nie je v Tennis Abstract“ sa zatiaľ ukladá iba do runtime."
)

st.subheader("🧪 Raw Flashscore diagnostika")

for raw_file in [
    "data/raw_flashscore/today.txt",
    "data/raw_flashscore/day_plus_1.txt",
]:
    if os.path.exists(raw_file):
        with open(raw_file, "rb") as f:
            st.download_button(
                f"⬇️ {raw_file}",
                data=f.read(),
                file_name=os.path.basename(raw_file),
                mime="text/plain",
                use_container_width=True,
            )
