import hashlib
import random


def profile_rng(seed: int, index: int) -> random.Random:
    """Stable independent stream: worker order can never change a record."""
    digest = hashlib.sha256(f"{seed}:profile:{index}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def choose(rng: random.Random, values: list[str], weights: list[float] | None = None) -> str:
    return rng.choices(values, weights=weights, k=1)[0]


def level(value: float) -> str:
    return "High" if value >= .67 else "Low" if value <= .33 else "Moderate"
