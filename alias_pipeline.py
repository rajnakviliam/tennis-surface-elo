import os

import pandas as pd


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
    except Exception:
        return pd.DataFrame()


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

    aliases = read_csv_if_exists(
        "aliases.csv"
    )

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
            [
                aliases,
                pd.DataFrame(rows_to_add),
            ],
            ignore_index=True,
        )

        aliases.to_csv(
            "aliases.csv",
            sep=";",
            index=False,
            encoding="utf-8-sig",
        )

    return len(rows_to_add), skipped_collision
