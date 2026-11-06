"""Validation and sanitization utilities for audio tags and user inputs."""
from __future__ import annotations

import re


def sanitize_tag_string(val: str, max_length: int = 256) -> str:
    """
    Sanitize audio tag string by replacing NULL bytes and control characters with space,
    normalizing whitespace, and truncating to max_length.
    (CHALLENGE-004, TC-SAN-001, TC-SAN-002)
    """
    if not val:
        return ""

    # Replace newlines, carriage returns, tabs, and NULL bytes with space
    s = val.replace("\r", " ").replace("\n", " ").replace("\t", " ").replace("\0", " ")

    # Replace other ASCII control characters (0x00-0x1f except space, 0x7f) with space
    cleaned_chars = [
        " " if (ord(ch) < 32 or ord(ch) == 127) else ch
        for ch in s
    ]
    s = "".join(cleaned_chars)

    # Normalize multiple spaces to a single space
    s = re.sub(r" +", " ", s).strip()

    # Truncate to max_length
    if len(s) > max_length:
        s = s[:max_length].strip()

    return s


def parse_and_validate_fractional_tag(val: str, field_name: str = "track") -> tuple[int, int]:
    """
    Parse and validate numeric or fractional tag (e.g. '1' or '1/12').
    Returns (number, total).
    Raises ValueError on invalid formats, 0, negative numbers, numbers > 999,
    or when number exceeds total (CHALLENGE-004, TC-VAL-001 - TC-VAL-005).
    """
    if not val or not str(val).strip():
        raise ValueError(f"{field_name.capitalize()} value cannot be empty.")

    s = str(val).strip()

    # Match "X" or "X/Y"
    pattern = r"^(\d+)(?:\s*/\s*(\d+))?$"
    match = re.match(pattern, s)
    if not match:
        raise ValueError(f"Invalid {field_name} format: '{val}'. Expected positive integer or 'X/Y'.")

    num_str, total_str = match.groups()
    num = int(num_str)
    total = int(total_str) if total_str is not None else 0

    if num < 1:
        raise ValueError(f"{field_name.capitalize()} number must be greater than or equal to 1, got {num}.")
    if num > 999:
        raise ValueError(f"{field_name.capitalize()} number cannot exceed 999, got {num}.")

    if total_str is not None:
        if total < 1:
            raise ValueError(f"Total {field_name}s must be greater than or equal to 1, got {total}.")
        if total > 999:
            raise ValueError(f"Total {field_name}s cannot exceed 999, got {total}.")
        if num > total:
            raise ValueError(
                f"{field_name.capitalize()} number ({num}) cannot exceed total {field_name}s ({total})."
            )

    return num, total


def validate_date_string(val: str) -> str:
    """
    Validate release year or date string.
    Empty string is allowed. If non-empty, must be a 4-digit year (1000-9999)
    or standard date format (YYYY-MM-DD).
    (TC-VAL-006, TC-EDIT-003)
    """
    if not val or not val.strip():
        return ""

    s = val.strip()
    year_match = re.match(r"^(\d{4})(?:-\d{2}-\d{2})?$", s)
    if not year_match:
        raise ValueError(f"Invalid date format: '{val}'. Expected 4-digit year (e.g. 2024).")

    year = int(year_match.group(1))
    if year < 1000 or year > 9999:
        raise ValueError(f"Year must be between 1000 and 9999, got {year}.")

    return s
