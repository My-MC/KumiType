"""Unicode selection policy with explicit overrides and protected PUA."""
import unicodedata

# Script and punctuation ranges are explicit: EAW alone cannot replace Latin.
JAPANESE_RANGES = (
    (0x2E80, 0x2FFF), (0x3000, 0x30FF), (0x31F0, 0x31FF),
    (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
    (0xFF01, 0xFF60), (0xFF61, 0xFF9F), (0xFFE0, 0xFFE6),
    (0x1B000, 0x1B16F), (0x20000, 0x2FA1F), (0x30000, 0x3347F),
)


def private_use(codepoint: int) -> bool:
    return (0xE000 <= codepoint <= 0xF8FF or
            0xF0000 <= codepoint <= 0xFFFFD or
            0x100000 <= codepoint <= 0x10FFFD)


def japanese_priority(codepoint: int, overrides: dict[int, str] | None = None) -> bool:
    if private_use(codepoint):
        return False
    preference = (overrides or {}).get(codepoint)
    if preference is not None:
        if preference not in ('cascadia', 'japanese'):
            raise ValueError(f'Invalid Unicode preference: {preference}')
        return preference == 'japanese'
    return any(start <= codepoint <= end for start, end in JAPANESE_RANGES)


def cell_count(codepoint: int) -> int:
    return 2 if unicodedata.east_asian_width(chr(codepoint)) in ('W', 'F') else 1


def select_codepoints(base: dict[int, str], japanese: dict[int, str],
                      overrides: dict[int, str] | None = None) -> list[int]:
    return sorted(cp for cp in japanese if not private_use(cp) and
                  (cp not in base or japanese_priority(cp, overrides)))
