"""
validation.py — Post-LLM validation for parsed transactions

Verifies LLM output against the source PDF text to catch hallucinations:
- Amount-in-text check: does the parsed amount actually appear in the PDF?
- Date validation: is the date parseable and in a reasonable range?
- Sanity bounds: is the amount within realistic IDR range?

Returns only validated transactions + count of rejected ones.
"""

import re
from datetime import datetime


def amount_to_text_formats(amount: float) -> list[str]:
    """
    Convert a numeric amount to possible IDR text representations.
    Example: 1500000 -> ["1.500.000", "1,500,000", "1500000"]
    """
    int_amount = int(abs(amount))
    formats = [str(int_amount)]

    # Dot-separated (BCA style): 1.500.000
    dot_fmt = f"{int_amount:,}".replace(",", ".")
    formats.append(dot_fmt)

    # Comma-separated (OCBC style): 1,500,000
    comma_fmt = f"{int_amount:,}"
    formats.append(comma_fmt)

    return formats


def validate_transactions(transactions: list[dict], full_text: str) -> tuple[list[dict], int]:
    """
    Validate LLM-parsed transactions against the source PDF text.

    Checks:
    1. Amount appears somewhere in the original text (anti-hallucination)
    2. Date is parseable as YYYY-MM-DD and in reasonable range
    3. Amount is within sanity bounds (0 < amount < 1 billion IDR)

    Returns:
        (valid_transactions, rejected_count)
    """
    valid = []
    rejected = 0

    for tx in transactions:
        # --- Date validation ---
        try:
            dt = datetime.strptime(tx["date"], "%Y-%m-%d")
            # Reasonable range: not before 2000, not in the far future
            if dt.year < 2000 or dt.year > datetime.now().year + 2:
                rejected += 1
                continue
        except (ValueError, KeyError):
            rejected += 1
            continue

        # --- Amount sanity bounds ---
        try:
            amount = float(tx["amount"])
            if amount <= 0 or amount >= 1_000_000_000:
                rejected += 1
                continue
        except (ValueError, KeyError, TypeError):
            rejected += 1
            continue

        # --- Amount-in-text check ---
        text_formats = amount_to_text_formats(amount)
        found_in_text = any(fmt in full_text for fmt in text_formats)
        if not found_in_text:
            # Try without leading zeros or with slight variations
            # Also check the raw integer
            raw_int_str = str(int(amount))
            found_in_text = raw_int_str in full_text.replace(".", "").replace(",", "")

        if not found_in_text:
            rejected += 1
            continue

        valid.append(tx)

    return valid, rejected
