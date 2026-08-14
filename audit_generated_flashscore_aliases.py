import pandas as pd
from pathlib import Path

FLASH_FILE = "flashscore_matches.csv"
CURRENT_ALIASES_FILE = "aliases.csv"
GENERATED_FILE = "flashscore_generated_aliases.csv"

OUTPUT_SUMMARY = "flashscore_alias_audit_summary.csv"
OUTPUT_RESOLVED_NEW = "flashscore_alias_resolved_by_generator.csv"
OUTPUT_UNRESOLVED = "flashscore_alias_still_unresolved.csv"

SEP = ";"


def clean(value):
    return " ".join(
        str(value or "")
        .replace("\xa0", " ")
        .strip()
        .split()
    )


def read_csv(path):
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Nenašiel som súbor: {path}")
    df = pd.read_csv(path, sep=SEP)
    df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]
    return df


def detect_alias_columns(df):
    lower = {c.casefold(): c for c in df.columns}
    alias_candidates = ["alias", "flashscore", "flashscore_name", "source_name"]
    player_candidates = [
        "player", "canonical", "canonical_name",
        "ta_name", "tennisabstract", "tennis_abstract"
    ]
    alias_col = next((lower[n] for n in alias_candidates if n in lower), None)
    player_col = next((lower[n] for n in player_candidates if n in lower), None)
    tour_col = lower.get("tour")

    if alias_col is None:
        alias_col = df.columns[0]
    if player_col is None and len(df.columns) >= 2:
        player_col = df.columns[1]

    return alias_col, player_col, tour_col


def build_lookup(df):
    alias_col, player_col, tour_col = detect_alias_columns(df)
    lookup = {}

    for _, row in df.iterrows():
        alias = clean(row.get(alias_col, ""))
        if not alias:
            continue

        player = clean(row.get(player_col, "") if player_col else "")
        tour = clean(row.get(tour_col, "") if tour_col else "")
        key = (tour.casefold(), alias.casefold())
        lookup.setdefault(key, set()).add(player)

    return lookup


def current_flashscore_players(df):
    required = {"DateLabel", "Tour", "Player 1", "Player 2"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "Vo flashscore_matches.csv chýbajú stĺpce: "
            + ", ".join(sorted(missing))
        )

    df = df[
        df["DateLabel"].astype(str).str.strip().isin(["Today", "Day+1"])
    ].copy()

    rows = []
    for _, row in df.iterrows():
        tour = clean(row["Tour"])

        for side in ["Player 1", "Player 2"]:
            player = clean(row[side])
            if player:
                rows.append({"FlashscoreName": player, "Tour": tour})

    return pd.DataFrame(rows).drop_duplicates().reset_index(drop=True)


def resolve_name(name, tour, lookup):
    matches = set()

    for key in [
        (tour.casefold(), name.casefold()),
        ("", name.casefold()),
    ]:
        matches |= lookup.get(key, set())

    matches.discard("")
    return sorted(matches)


def main():
    flash = read_csv(FLASH_FILE)
    current_aliases = read_csv(CURRENT_ALIASES_FILE)
    generated = read_csv(GENERATED_FILE)

    current_lookup = build_lookup(current_aliases)
    generated_lookup = build_lookup(generated)

    players = current_flashscore_players(flash)

    if players.empty:
        print("Nenašli sa žiadni hráči v Today/Day+1.")
        return

    audit_rows = []
    new_rows = []
    unresolved_rows = []

    for _, row in players.iterrows():
        fs_name = clean(row["FlashscoreName"])
        tour = clean(row["Tour"])

        existing_matches = resolve_name(fs_name, tour, current_lookup)
        generated_matches = resolve_name(fs_name, tour, generated_lookup)

        if len(existing_matches) == 1:
            status = "EXISTING_ALIAS"
            resolved_player = existing_matches[0]

        elif len(existing_matches) > 1:
            status = "EXISTING_COLLISION"
            resolved_player = " | ".join(existing_matches)

        elif len(generated_matches) == 1:
            status = "RESOLVED_BY_GENERATOR"
            resolved_player = generated_matches[0]
            new_rows.append({
                "FlashscoreName": fs_name,
                "Tour": tour,
                "ResolvedPlayer": resolved_player,
            })

        elif len(generated_matches) > 1:
            status = "GENERATED_COLLISION"
            resolved_player = " | ".join(generated_matches)
            unresolved_rows.append({
                "FlashscoreName": fs_name,
                "Tour": tour,
                "Reason": status,
                "Candidates": resolved_player,
            })

        else:
            status = "UNRESOLVED"
            resolved_player = ""
            unresolved_rows.append({
                "FlashscoreName": fs_name,
                "Tour": tour,
                "Reason": status,
                "Candidates": "",
            })

        audit_rows.append({
            "FlashscoreName": fs_name,
            "Tour": tour,
            "Status": status,
            "ResolvedPlayer": resolved_player,
        })

    audit = pd.DataFrame(audit_rows)

    summary = (
        audit["Status"]
        .value_counts()
        .rename_axis("Status")
        .reset_index(name="Count")
    )

    summary.to_csv(
        OUTPUT_SUMMARY,
        sep=SEP,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(new_rows).to_csv(
        OUTPUT_RESOLVED_NEW,
        sep=SEP,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(unresolved_rows).to_csv(
        OUTPUT_UNRESOLVED,
        sep=SEP,
        index=False,
        encoding="utf-8-sig",
    )

    total_unique = len(audit)
    existing = int((audit["Status"] == "EXISTING_ALIAS").sum())
    new_resolved = int((audit["Status"] == "RESOLVED_BY_GENERATOR").sum())
    unresolved = int(
        audit["Status"].isin(
            ["UNRESOLVED", "EXISTING_COLLISION", "GENERATED_COLLISION"]
        ).sum()
    )

    print("=" * 72)
    print("AUDIT GENEROVANYCH FLASHSCORE ALIASOV")
    print("=" * 72)
    print(f"Unikátnych Flashscore hráčov Today + Day+1: {total_unique}")
    print(f"Už pokrytých existujúcim aliases.csv:        {existing}")
    print(f"Navyše vyriešených generátorom:              {new_resolved}")
    print(f"Stále nevyriešených / kolíznych:             {unresolved}")
    print()
    print(f"SUMMARY:    {OUTPUT_SUMMARY}")
    print(f"NEW FIXES:  {OUTPUT_RESOLVED_NEW}")
    print(f"UNRESOLVED: {OUTPUT_UNRESOLVED}")
    print("=" * 72)


if __name__ == "__main__":
    main()
