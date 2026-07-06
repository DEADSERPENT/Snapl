"""
Base62 encode/decode for collision-free short codes.

The auto-incremented DB row ID is the source of uniqueness — we just
encode it into a compact, URL-safe string. No random generation, no
collision checking required.

Alphabet: digits 0-9, lowercase a-z, uppercase A-Z  (62 chars total).
"""

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)  # 62


def encode(n: int) -> str:
    if n == 0:
        return ALPHABET[0]
    digits = []
    while n:
        digits.append(ALPHABET[n % BASE])
        n //= BASE
    return "".join(reversed(digits))


def decode(s: str) -> int:
    result = 0
    for char in s:
        result = result * BASE + ALPHABET.index(char)
    return result
