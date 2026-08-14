import pandas as pd
from pathlib import Path

INPUT_FILE = "players_master.csv"
OUTPUT_SAFE = "flashscore_generated_aliases.csv"
OUTPUT_COLLISIONS = "flashscore_alias_collisions.csv"
OUTPUT_REVIEW = "flashscore_alias_review_4plus.csv"

SEP = ";"


def clean_name(name):
    return " ".join(str(name).replace("\xa0", " ").split()).strip()


def initial(word):
    word = clean_name(word)
    return f"{word[0].upper()}." if word else ""


def generate_aliases(player):
    player = clean_name(player)
    parts = player.split()

    if len(parts) == 2:
        first, last = parts
        return [f"{last} {initial(first)}"]

    if len(parts) == 3:
        first, middle, last = parts
        return [
            f"{middle} {last} {initial(first)}",
            f"{last} {initial(first)} {initial(middle)}",
        ]

    return []


def main():
    input_path = Path(INPUT_FILE)

    if not input_path.exists():
        raise FileNotFoundError(
            f"Nenašiel som {INPUT_FILE} v aktuálnom priečinku."
        )

    df = pd.read_csv(input_path, sep=SEP)

    required = {"Player", "Tour"}
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "V players_master.csv chýbajú stĺpce: "
            + ", ".join(sorted(missing))
        )

    rows = []
    review_rows = []

    for _, row in df.iterrows():
        player = clean_name(row["Player"])
        tour = clean_name(row["Tour"])

        if not player:
            continue

        parts = player.split()
        aliases = generate_aliases(player)

        if len(parts) >= 4:
            review_rows.append(
                {
                    "Player": player,
                    "Tour": tour,
                    "WordCount": len(parts),
                }
            )
            continue

        for alias in aliases:
            rows.append(
                {
                    "Alias": clean_name(alias),
                    "Player": player,
                    "Tour": tour,
                    "WordCount": len(parts),
                }
            )

    generated = pd.DataFrame(rows)

    if generated.empty:
        print("Nevygenerovali sa žiadne aliasy.")
        return

    unique_targets = (
        generated
        .groupby(["Tour", "Alias"])["Player"]
        .nunique()
        .reset_index(name="PlayerCount")
    )

    ambiguous_keys = set(
        tuple(x)
        for x in unique_targets[
            unique_targets["PlayerCount"] > 1
        ][["Tour", "Alias"]].itertuples(index=False, name=None)
    )

    generated["Collision"] = generated.apply(
        lambda r: (r["Tour"], r["Alias"]) in ambiguous_keys,
        axis=1,
    )

    safe = (
        generated[~generated["Collision"]]
        .drop(columns=["Collision"])
        .drop_duplicates(subset=["Tour", "Alias", "Player"])
        .sort_values(["Tour", "Alias", "Player"])
    )

    collisions = (
        generated[generated["Collision"]]
        .drop(columns=["Collision"])
        .drop_duplicates(subset=["Tour", "Alias", "Player"])
        .sort_values(["Tour", "Alias", "Player"])
    )

    review = pd.DataFrame(review_rows)
    if not review.empty:
        review = (
            review.drop_duplicates()
            .sort_values(["Tour", "WordCount", "Player"])
        )

    safe.to_csv(
        OUTPUT_SAFE,
        sep=SEP,
        index=False,
        encoding="utf-8-sig",
    )

    collisions.to_csv(
        OUTPUT_COLLISIONS,
        sep=SEP,
        index=False,
        encoding="utf-8-sig",
    )

    review.to_csv(
        OUTPUT_REVIEW,
        sep=SEP,
        index=False,
        encoding="utf-8-sig",
    )

    print("=" * 68)
    print("FLASHSCORE ALIAS GENERATOR")
    print("=" * 68)
    print(f"Hráčov v players_master:      {len(df)}")
    print(f"Bezpečných aliasov:           {len(safe)}")
    print(f"Kolíznych aliasov:            {len(collisions)}")
    print(f"Hráčov so 4+ slovami:         {len(review)}")
    print()
    print(f"SAFE:       {OUTPUT_SAFE}")
    print(f"COLLISIONS: {OUTPUT_COLLISIONS}")
    print(f"REVIEW:     {OUTPUT_REVIEW}")
    print("=" * 68)


if __name__ == "__main__":
    main()
