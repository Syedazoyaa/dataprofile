import hashlib
import random


def profile_rng(seed: int, index: int) -> random.Random:
    """Stable independent stream: worker order can never change a record."""
    digest = hashlib.sha256(f"{seed}:profile:{index}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def choose(rng: random.Random, values: list[str], weights: list[float] | None = None) -> str:
    return rng.choices(values, weights=weights, k=1)[0]


def level(value: float) -> str:
    # Narrowed moderate band to reduce excessive Moderate dominance (was 0.33/0.67 → 34% width)
    # Now 0.40/0.60 → 20% width, allowing more High/Low differentiation while preserving vocabulary
    # Internal 0-100 (0-1) still used; mapping is the display layer
    return "High" if value >= .60 else "Low" if value <= .40 else "Moderate"
