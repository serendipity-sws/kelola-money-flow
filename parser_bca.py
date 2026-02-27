"""
parser_bca.py — BCA bank statement parsers

Handles:
- BCA Credit Card statements (DD-MMM DD-MMM pattern, dots as thousands sep)
- BCA Account statements (DD/MM pattern, tabungan/giro)

Both return DataFrames matching the standard contract:
  date, description, amount, transaction_type, category, card, source
"""

import re
from datetime import datetime

import pandas as pd

from parser_core import INDO_MONTHS, decrypt_pdf_bytes, parse_idr_amount
from categories import (
    categorize_transaction,
    EXPENSE_RULES,
    CREDIT_RULES,
    ACCOUNT_RULES,
)

import pdfplumber


# ---------------------------------------------------------------------------
# BCA Credit Card Statement Parser
#
# Format observed from real PDF:
#   Page text contains transaction lines like:
#     DD-MMM DD-MMM DESCRIPTION AMOUNT [CR]
#   Where:
#     - First DD-MMM = transaction date
#     - Second DD-MMM = posting date
#     - CR suffix = credit (payment/refund)
#   Sections separated by card names: "BCA EVERYDAY CARD", "VISA CARD", etc.
#   Summary rows: "SALDO SEBELUMNYA", "SUBTOTAL", "TOTAL"
#   Statement date in header: "TANGGAL REKENING : 25 JANUARI 2026"
# ---------------------------------------------------------------------------

# Lines to skip — these are summary/header rows, not transactions
BCA_CC_SKIP_PATTERNS = [
    re.compile(r"^SALDO SEBELUMNYA", re.IGNORECASE),
    re.compile(r"^SUBTOTAL", re.IGNORECASE),
    re.compile(r"^TOTAL\b", re.IGNORECASE),
    re.compile(r"^TAGIHAN", re.IGNORECASE),
    re.compile(r"^PEMBAYARAN MINIMUM", re.IGNORECASE),
    re.compile(r"^KUALITAS KREDIT", re.IGNORECASE),
    re.compile(r"SUKU BUNGA", re.IGNORECASE),
    re.compile(r"^KREDIT LIMIT", re.IGNORECASE),
    re.compile(r"^BATAS TARIK", re.IGNORECASE),
    re.compile(r"^REKENING KARTU", re.IGNORECASE),
    re.compile(r"^NOMOR CUSTOMER", re.IGNORECASE),
    re.compile(r"^TANGGAL (REKENING|JATUH)", re.IGNORECASE),
    re.compile(r"^\d{4}-\d{2}XX", re.IGNORECASE),   # masked card number
    re.compile(r"^INFORMASI", re.IGNORECASE),
    re.compile(r"^PROMO ", re.IGNORECASE),
    re.compile(r"^DISKON ", re.IGNORECASE),
    re.compile(r"^\d+ / \d+$"),  # page number like "1 / 2"
]

# Pattern: DD-MMM DD-MMM <description> <amount> [CR]
# Examples:
#   25-JAN 25-JAN ATPY XL JAN 087809919227 166.500
#   29-DES 29-DES PEMBAYARAN - MYBCA 167.166 CR
#   10-JAN 10-JAN CICILAN BCA KE 04 DARI 12, IBOX WAIVE GR 1.979.083
BCA_CC_TRANSACTION_PATTERN = re.compile(
    r"^(\d{2})-([A-Z]{3})\s+(\d{2})-([A-Z]{3})\s+(.+?)\s+([\d.]+)\s*(CR)?$",
    re.IGNORECASE,
)


def parse_bca_credit_card(pdf_bytes: bytes, password: str = "") -> pd.DataFrame:
    """
    Parse a BCA credit card statement.

    Extracts the statement year from the header, then parses each
    transaction line using the DD-MMM DD-MMM pattern.
    """
    decrypted_buffer = decrypt_pdf_bytes(pdf_bytes, password)
    transactions = []

    # We need the statement year from the header (e.g., "25 JANUARI 2026")
    statement_year = None
    statement_month = None
    current_card = "Kartu Kredit BCA"

    with pdfplumber.open(decrypted_buffer) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Extract statement year from header
                # Pattern: "TANGGAL REKENING : 25 JANUARI 2026"
                year_match = re.search(
                    r"TANGGAL REKENING\s*:\s*\d+\s+\w+\s+(\d{4})",
                    line, re.IGNORECASE,
                )
                if year_match:
                    statement_year = int(year_match.group(1))
                    # Also grab month for resolving cross-year dates
                    month_match = re.search(
                        r"TANGGAL REKENING\s*:\s*\d+\s+(\w+)\s+\d{4}",
                        line, re.IGNORECASE,
                    )
                    if month_match:
                        month_name = month_match.group(1).upper()[:3]
                        statement_month = INDO_MONTHS.get(month_name, 1)

                # Track which card section we're in
                if "EVERYDAY CARD" in line.upper():
                    current_card = "BCA Everyday"
                elif "VISA CARD" in line.upper():
                    current_card = "BCA Visa"
                elif "MASTERCARD" in line.upper():
                    current_card = "BCA Mastercard"

                # Skip non-transaction lines
                should_skip = False
                for skip_pat in BCA_CC_SKIP_PATTERNS:
                    if skip_pat.search(line):
                        should_skip = True
                        break
                if should_skip:
                    continue

                # Try matching transaction pattern
                match = BCA_CC_TRANSACTION_PATTERN.match(line)
                if not match:
                    continue

                trans_day = int(match.group(1))
                trans_month_abbr = match.group(2).upper()
                # post_day = int(match.group(3))  # posting date — we use transaction date
                # post_month_abbr = match.group(4).upper()
                description = match.group(5).strip()
                amount_raw = match.group(6)
                is_credit = match.group(7) is not None  # "CR" suffix

                trans_month = INDO_MONTHS.get(trans_month_abbr)
                if not trans_month:
                    continue

                # Resolve year: if statement is JAN and transaction is DES,
                # the transaction was in the previous year
                year = statement_year or datetime.now().year
                if statement_month and trans_month > statement_month and (trans_month - statement_month) > 6:
                    year -= 1

                try:
                    trans_date = datetime(year, trans_month, trans_day)
                except ValueError:
                    continue

                amount = parse_idr_amount(amount_raw)
                if amount == 0:
                    continue

                # Credit card: CR = payment (money coming in to pay off card)
                # Non-CR = purchase/charge (money going out)
                if is_credit:
                    transaction_type = "income"
                    category = categorize_transaction(description, CREDIT_RULES, fallback="Pembayaran Kartu")
                else:
                    transaction_type = "expense"
                    category = categorize_transaction(description, EXPENSE_RULES)
                    amount = -amount  # Expenses are negative

                transactions.append({
                    "date": trans_date,
                    "description": description,
                    "amount": amount,
                    "transaction_type": transaction_type,
                    "category": category,
                    "card": current_card,
                })

    if not transactions:
        raise ValueError(
            "Tidak ditemukan transaksi di rekening kartu kredit BCA. "
            "Pastikan file yang diupload benar."
        )

    df = pd.DataFrame(transactions)
    df["source"] = "BCA Kartu Kredit"
    df = df.sort_values("date").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# BCA Account Statement Parser (rekening tabungan / giro)
# Placeholder — will be refined when we see a real sample
# ---------------------------------------------------------------------------

def parse_bca_account(pdf_bytes: bytes, password: str = "") -> pd.DataFrame:
    """
    Parse a BCA account (tabungan/giro) statement.

    Typical format: DD/MM | Description | CBG | Debit | Credit | Balance
    or text-based with similar pattern.
    """
    decrypted_buffer = decrypt_pdf_bytes(pdf_bytes, password)
    transactions = []

    # Try to extract year from header
    statement_year = datetime.now().year

    with pdfplumber.open(decrypted_buffer) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""

            # Look for year in header
            year_match = re.search(r"PERIODE\s*:?\s*.*?(\d{4})", text, re.IGNORECASE)
            if year_match:
                statement_year = int(year_match.group(1))

            # BCA account statements typically have lines like:
            # DD/MM DESCRIPTION AMOUNT DB/CR BALANCE
            lines = text.split("\n")
            for line in lines:
                line = line.strip()

                # Pattern: DD/MM DESCRIPTION amounts...
                match = re.match(
                    r"^(\d{2}/\d{2})\s+(.+?)\s+([\d,.]+)\s*(DB|CR|)(?:\s+([\d,.]+))?",
                    line,
                    re.IGNORECASE,
                )
                if not match:
                    continue

                date_str = match.group(1)  # DD/MM
                description = match.group(2).strip()
                amount_raw = match.group(3)
                dc_flag = match.group(4).upper() if match.group(4) else ""

                # Skip header-like rows
                if description.lower() in ("keterangan", "description", "tanggal"):
                    continue

                day, month = date_str.split("/")
                try:
                    trans_date = datetime(statement_year, int(month), int(day))
                except ValueError:
                    continue

                amount = parse_idr_amount(amount_raw)
                if amount == 0:
                    continue

                # DB = debit (money out), CR = credit (money in)
                if dc_flag == "DB":
                    amount = -abs(amount)
                    transaction_type = "expense"
                elif dc_flag == "CR":
                    amount = abs(amount)
                    transaction_type = "income"
                else:
                    transaction_type = "expense" if amount < 0 else "income"

                if transaction_type == "income":
                    category = categorize_transaction(description, ACCOUNT_RULES, fallback="Pendapatan Lain")
                else:
                    category = categorize_transaction(description, ACCOUNT_RULES, fallback="Pengeluaran Lain")

                transactions.append({
                    "date": trans_date,
                    "description": description,
                    "amount": amount,
                    "transaction_type": transaction_type,
                    "category": category,
                })

    if not transactions:
        raise ValueError(
            "Tidak ditemukan transaksi di rekening koran BCA. "
            "Pastikan file yang diupload benar."
        )

    df = pd.DataFrame(transactions)
    df["source"] = "BCA Rekening"
    df = df.sort_values("date").reset_index(drop=True)
    return df
