"""Fuzzy name matching for company search results."""

import re

# Words to strip when comparing company names
NOISE_WORDS = {
    "inc", "inc.", "incorporated", "corp", "corp.", "corporation",
    "llc", "l.l.c.", "ltd", "ltd.", "limited", "co", "co.",
    "company", "group", "holdings", "international", "intl",
    "the", "of", "and", "&", "a", "an",
    "foundation", "fund", "trust", "association", "assoc",
    "org", "organization", "society",
}


def normalize(name: str) -> str:
    """Lowercase, strip punctuation and noise words."""
    name = name.lower().strip()
    name = re.sub(r"[.,\-'\"!()]+", " ", name)
    words = [w for w in name.split() if w not in NOISE_WORDS]
    return " ".join(words)


def name_similarity(a: str, b: str) -> float:
    """Token-based similarity score between two company names (0.0 to 1.0).

    Uses Jaccard similarity on normalized word tokens.
    """
    tokens_a = set(normalize(a).split())
    tokens_b = set(normalize(b).split())

    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b

    return len(intersection) / len(union)


def is_match(query: str, candidate: str, threshold: float = 0.4) -> bool:
    """Check if candidate name is a reasonable match for query.

    Also checks if all query tokens appear as substrings in the candidate.
    """
    sim = name_similarity(query, candidate)
    if sim >= threshold:
        return True

    # Substring check: all significant query words present in candidate
    q_tokens = set(normalize(query).split())
    c_lower = normalize(candidate)
    if q_tokens and all(t in c_lower for t in q_tokens):
        return True

    return False


def best_match(query: str, candidates: list[dict],
               name_key: str = "name",
               threshold: float = 0.3) -> dict | None:
    """Find the best matching candidate from a list.

    Returns the candidate dict with highest similarity above threshold,
    or None if no match.
    """
    best = None
    best_score = 0.0

    for c in candidates:
        cname = c.get(name_key, "")
        if not cname:
            continue
        score = name_similarity(query, cname)
        if score > best_score:
            best_score = score
            best = c

    if best_score >= threshold:
        return best
    return None
