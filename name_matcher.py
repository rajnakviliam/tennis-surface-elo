
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable


@dataclass(frozen=True)
class NameVariant:
    surname: str
    initials: tuple[str, ...]


@dataclass
class PlayerRecord:
    name: str
    tour: str
    normalized: str
    variants: list[NameVariant] = field(default_factory=list)


@dataclass
class MatchResult:
    matched: bool
    source_name: str
    matched_name: str = ""
    tour: str = ""
    confidence: float = 0.0
    reason: str = ""


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = text.replace("-", " ").replace("'", " ").replace("’", " ")
    text = re.sub(r"[^a-z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def split_source_name(source_name: str) -> tuple[str, tuple[str, ...]]:
    parts = normalize_name(source_name).split()
    if not parts:
        return "", tuple()

    first_initial = next(
        (i for i, token in enumerate(parts) if len(token) == 1),
        None,
    )

    if first_initial is None:
        return " ".join(parts), tuple()

    return " ".join(parts[:first_initial]), tuple(parts[first_initial:])


def generate_target_variants(target_name: str) -> list[NameVariant]:
    parts = normalize_name(target_name).split()
    if len(parts) < 2:
        return [NameVariant(" ".join(parts), tuple())] if parts else []

    variants: set[NameVariant] = set()
    max_surname_words = min(3, len(parts) - 1)

    for surname_words in range(1, max_surname_words + 1):
        split_at = len(parts) - surname_words
        given = parts[:split_at]
        surname_tokens = parts[split_at:]
        initials = tuple(token[0] for token in given if token)

        for start in range(len(surname_tokens)):
            for end in range(start + 1, len(surname_tokens) + 1):
                variants.add(
                    NameVariant(
                        surname=" ".join(surname_tokens[start:end]),
                        initials=initials,
                    )
                )

    return sorted(
        variants,
        key=lambda v: (len(v.surname.split()), len(v.initials)),
        reverse=True,
    )


def initials_quality(
    source_initials: tuple[str, ...],
    target_initials: tuple[str, ...],
) -> tuple[bool, float, str]:
    """
    Tennis weby niekedy používajú druhé krstné meno:
      Ruse G. -> Elena Gabriela Ruse

    Preto:
    - presná zhoda iniciál = 1.00
    - jedna iniciála obsiahnutá medzi krstnými menami = 0.99
    - viac iniciál musí sedieť v rovnakom poradí = 0.98
    """
    if not source_initials:
        return True, 0.95, "no_source_initials"

    if source_initials == target_initials:
        return True, 1.00, "exact_initials"

    if len(source_initials) == 1 and source_initials[0] in target_initials:
        return True, 0.99, "initial_found_in_given_names"

    if len(source_initials) > 1:
        position = 0
        for initial in target_initials:
            if position < len(source_initials) and initial == source_initials[position]:
                position += 1
        if position == len(source_initials):
            return True, 0.98, "initials_in_order"

    return False, 0.0, "initials_mismatch"


def surname_score(source: str, target: str) -> float:
    if not source or not target:
        return 0.0
    if source == target:
        return 1.0

    if source.replace(" ", "") == target.replace(" ", ""):
        return 0.995

    return SequenceMatcher(None, source, target).ratio()


def build_player_records(
    players: Iterable[tuple[str, str]],
) -> list[PlayerRecord]:
    return [
        PlayerRecord(
            name=name,
            tour=tour.upper(),
            normalized=normalize_name(name),
            variants=generate_target_variants(name),
        )
        for name, tour in players
        if name
    ]


def match_name(
    source_name: str,
    candidates: Iterable[PlayerRecord],
    source_tour: str | None = None,
    minimum_confidence: float = 90.0,
) -> MatchResult:
    source_surname, source_initials = split_source_name(source_name)
    source_tour = (source_tour or "").upper().strip()

    if not source_surname:
        return MatchResult(False, source_name, reason="empty_source_name")

    scored: list[tuple[float, PlayerRecord, str]] = []

    for candidate in candidates:
        if source_tour and candidate.tour != source_tour:
            continue

        best_score = 0.0
        best_reason = ""

        for variant in candidate.variants:
            initials_ok, initials_factor, initials_reason = initials_quality(
                source_initials,
                variant.initials,
            )
            if not initials_ok:
                continue

            s_score = surname_score(source_surname, variant.surname)
            if s_score < 0.84:
                continue

            confidence = round(s_score * initials_factor * 100, 1)

            if s_score == 1.0:
                reason = f"exact_surname_variant_and_{initials_reason}"
            elif s_score >= 0.995:
                reason = f"normalized_surname_variant_and_{initials_reason}"
            else:
                reason = f"fuzzy_surname_variant_and_{initials_reason}"

            if confidence > best_score:
                best_score = confidence
                best_reason = reason

        if best_score:
            scored.append((best_score, candidate, best_reason))

    if not scored:
        return MatchResult(
            False,
            source_name,
            reason="no_candidate_in_elo_for_tour",
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    best_confidence, best_candidate, best_reason = scored[0]

    if len(scored) > 1:
        second_confidence, second_candidate, _ = scored[1]
        if (
            best_candidate.name != second_candidate.name
            and best_confidence - second_confidence < 3.0
        ):
            return MatchResult(
                False,
                source_name,
                confidence=best_confidence,
                reason="ambiguous_match",
            )

    if best_confidence < minimum_confidence:
        return MatchResult(
            False,
            source_name,
            confidence=best_confidence,
            reason="below_confidence_threshold",
        )

    return MatchResult(
        True,
        source_name,
        matched_name=best_candidate.name,
        tour=best_candidate.tour,
        confidence=best_confidence,
        reason=best_reason,
    )


if __name__ == "__main__":
    sample_players = build_player_records([
        ("Roberto Bautista Agut", "ATP"),
        ("Alejandro Davidovich Fokina", "ATP"),
        ("Pablo Carreno Busta", "ATP"),
        ("Felix Auger Aliassime", "ATP"),
        ("Roman Andres Burruchaga", "ATP"),
        ("Luca Van Assche", "ATP"),
        ("Mackenzie Mcdonald", "ATP"),
        ("Elena Gabriela Ruse", "WTA"),
    ])

    tests = [
        ("Bautista R.", "ATP"),
        ("Davidovich Fokina A.", "ATP"),
        ("Carreno-Busta P.", "ATP"),
        ("Auger-Aliassime F.", "ATP"),
        ("Burruchaga R. A.", "ATP"),
        ("van Assche L.", "ATP"),
        ("Donald M.", "ATP"),
        ("Ruse G.", "WTA"),
    ]

    for name, tour in tests:
        print(match_name(name, sample_players, source_tour=tour))
