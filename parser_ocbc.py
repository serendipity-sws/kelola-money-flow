"""
parser_ocbc.py — OCBC bank statement parser

Handles:
- OCBC Credit Card statements (DD/MM DD/MM pattern, commas as thousands sep)

Returns DataFrames matching the standard contract:
  date, description, amount, transaction_type, category, card, source
"""

import re
from datetime import datetime

import pandas as pd
import pdfplumber

from parser_core import decrypt_pdf_bytes
from categories import (
    categorize_transaction,
    EXPENSE_RULES,
    CREDIT_RULES,
)


# ---------------------------------------------------------------------------
# OCBC Credit Card Statement Parser
#
# Format observed from real PDF:
#   DD/MM DD/MM DESCRIPTION AMOUNT [CR]
#   Where:
#     - First DD/MM = transaction date
#     - Second DD/MM = posting date
#     - CR suffix = credit (payment/refund), no CR = charge/expense
#     - Amounts use comma as thousands separator: 39,623,645
#   Statement year from header: "Tanggal Cetak Tagihan : DD-MM-YYYY"
#   Skip rows: LAST MONTH'S BALANCE, SUBTOTAL, TOTAL, RINGKASAN, BIAYA, etc.
# ---------------------------------------------------------------------------

# Lines to skip in OCBC statements
OCBC_SKIP_PATTERNS = [
    re.compile(r"^LAST MONTH", re.IGNORECASE),
    re.compile(r"^SUBTOTAL", re.IGNORECASE),
    re.compile(r"^TOTAL\b", re.IGNORECASE),
    re.compile(r"^RINGKASAN", re.IGNORECASE),
    re.compile(r"^BIAYA\b", re.IGNORECASE),
    re.compile(r"^STAMP DUTY", re.IGNORECASE),
    re.compile(r"^STATEMNT", re.IGNORECASE),
    re.compile(r"^INFORMASI", re.IGNORECASE),
]

# Pattern: DD/MM DD/MM <description> <amount> [CR]
# Amount uses commas as thousands separator: 39,623,645
OCBC_CC_TRANSACTION_PATTERN = re.compile(
    r"^(\d{2})/(\d{2})\s+\d{2}/\d{2}\s+(.+?)\s+([\d,]+)\s*(CR)?$",
    re.IGNORECASE,
)


def parse_ocbc_statement(pdf_bytes: bytes, password: str = "") -> pd.DataFrame:
    """
    Parse an OCBC credit card statement.

    Extracts statement year from header, then parses each transaction line
    using DD/MM DD/MM pattern.
    """
    decrypted_buffer = decrypt_pdf_bytes(pdf_bytes, password)
    transactions = []

    # Extract year from header: "Tanggal Cetak Tagihan : 18-02-2026"
    statement_year = None

    with pdfplumber.open(decrypted_buffer) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Extract statement year from header
                year_match = re.search(
                    r"Tanggal Cetak Tagihan\s*:\s*\d{2}-\d{2}-(\d{4})",
                    line, re.IGNORECASE,
                )
                if year_match:
                    statement_year = int(year_match.group(1))

                # Skip non-transaction rows
                should_skip = False
                for skip_pat in OCBC_SKIP_PATTERNS:
                    if skip_pat.search(line):
                        should_skip = True
                        break
                if should_skip:
                    continue

                # Try matching transaction pattern
                match = OCBC_CC_TRANSACTION_PATTERN.match(line)
                if not match:
                    continue

                trans_day = int(match.group(1))
                trans_month = int(match.group(2))
                description = match.group(3).strip()
                amount_raw = match.group(4)
                is_credit = match.group(5) is not None  # "CR" suffix

                year = statement_year or datetime.now().year
                try:
                    trans_date = datetime(year, trans_month, trans_day)
                except ValueError:
                    continue

                # OCBC uses commas as thousands separators: "39,623,645"
                amount = float(amount_raw.replace(",", ""))
                if amount == 0:
                    continue

                if is_credit:
                    transaction_type = "income"
                    category = categorize_transaction(description, CREDIT_RULES, fallback="Pembayaran Kartu")
                else:
                    transaction_type = "expense"
                    amount = -amount
                    category = categorize_transaction(description, EXPENSE_RULES)

                transactions.append({
                    "date": trans_date,
                    "description": description,
                    "amount": amount,
                    "transaction_type": transaction_type,
                    "category": category,
                })

    if not transactions:
        raise ValueError(
            "Tidak ditemukan transaksi di rekening OCBC. "
            "Pastikan file yang diupload benar."
        )

    df = pd.DataFrame(transactions)
    df["source"] = "OCBC Kartu Kredit"
    df = df.sort_values("date").reset_index(drop=True)
    return df
