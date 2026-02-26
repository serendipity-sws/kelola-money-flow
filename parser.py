"""
parser.py — PDF data extraction for Money Flow POC

Auto-detects bank and statement type from PDF content:
- BCA Credit Card Statement
- BCA Account Statement (tabungan/giro)
- OCBC Bank Statement
- Tokopedia / Shopee seller report

Returns normalized DataFrames with columns:
  date, description, amount, transaction_type, category, source
"""

import io
import re
from datetime import datetime

import pandas as pd
import pdfplumber
import pikepdf

from categories import (
    categorize_transaction,
    EXPENSE_RULES,
    CREDIT_RULES,
    ACCOUNT_RULES,
)


# ---------------------------------------------------------------------------
# Indonesian month abbreviation map (BCA uses abbreviated months like JAN, FEB, etc.)
# ---------------------------------------------------------------------------

INDO_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MEI": 5, "MAY": 5,
    "JUN": 6, "JUL": 7, "AGU": 8, "AGT": 8, "AUG": 8, "SEP": 9,
    "OKT": 10, "OCT": 10, "NOV": 11, "NOP": 11, "DES": 12, "DEC": 12,
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def check_pdf_encrypted(pdf_bytes: bytes) -> bool:
    """Check whether a PDF requires a password to open."""
    try:
        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            return False
    except pikepdf.PasswordError:
        return True
    except Exception:
        return False


def decrypt_pdf_bytes(pdf_bytes: bytes, password: str) -> io.BytesIO:
    """
    Decrypt a password-protected PDF and return a BytesIO object
    that pdfplumber can open directly.
    Returns the original bytes wrapped in BytesIO if no password needed.
    """
    # Try opening without password first
    try:
        with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
            return io.BytesIO(pdf_bytes)
    except pikepdf.PasswordError:
        pass

    # Decrypt with provided password
    if not password:
        raise ValueError("PDF ini dilindungi password. Silakan masukkan password.")

    try:
        with pikepdf.open(io.BytesIO(pdf_bytes), password=password) as pdf:
            output_buffer = io.BytesIO()
            pdf.save(output_buffer)
            output_buffer.seek(0)
            return output_buffer
    except pikepdf.PasswordError:
        raise ValueError("Password salah — PDF tidak bisa dibuka.")
    except Exception as exc:
        raise ValueError(f"Gagal membuka PDF: {exc}")


def extract_full_text(pdf_bytes: bytes, password: str = "") -> str:
    """Extract all text from all pages of a PDF. Used for auto-detection."""
    decrypted_buffer = decrypt_pdf_bytes(pdf_bytes, password)
    all_text = []
    with pdfplumber.open(decrypted_buffer) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            all_text.append(text)
    return "\n".join(all_text)


def parse_idr_amount(raw: str) -> float:
    """
    Convert an IDR string like '1.500.000' or '166.500' to a float.
    BCA uses dots as thousands separators (no decimal commas on statements).
    """
    cleaned = raw.strip().replace("Rp", "").replace("RP", "").replace(" ", "")
    # Handle negative indicators
    is_negative = cleaned.startswith("-") or cleaned.startswith("(")
    cleaned = cleaned.replace("-", "").replace("(", "").replace(")", "")
    # Remove thousands separators (dots)
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        value = float(cleaned)
        return -value if is_negative else value
    except ValueError:
        return 0.0


def format_idr(amount: float) -> str:
    """Format a float as IDR display string: Rp 1.500.000"""
    abs_amount = abs(amount)
    formatted = f"{abs_amount:,.0f}".replace(",", ".")
    prefix = "-" if amount < 0 else ""
    return f"{prefix}Rp {formatted}"


# ---------------------------------------------------------------------------
# Auto-detection: identify bank and statement type from PDF text
# ---------------------------------------------------------------------------

def detect_source(full_text: str) -> dict:
    """
    Analyze PDF text content and return metadata about the document.

    Returns dict with:
        bank: 'BCA' | 'OCBC' | 'unknown'
        statement_type: 'credit_card' | 'account' | 'marketplace' | 'unknown'
        display_name: human-readable name like 'BCA Kartu Kredit'
    """
    text_upper = full_text.upper()

    # --- BCA detection ---
    is_bca = any(k in text_upper for k in [
        "BCA", "BANK CENTRAL ASIA", "HALO BCA", "KLIKBCA", "BCA MOBILE",
        "MYBCA",
    ])

    if is_bca:
        # Credit card vs account statement
        is_credit_card = any(k in text_upper for k in [
            "KARTU KREDIT", "CREDIT CARD", "KREDIT LIMIT", "TAGIHAN BARU",
            "JATUH TEMPO", "PEMBAYARAN MINIMUM", "VISA CARD", "MASTERCARD",
            "BCA EVERYDAY CARD", "SUKU BUNGA PEMBELANJAAN",
        ])
        if is_credit_card:
            return {
                "bank": "BCA",
                "statement_type": "credit_card",
                "display_name": "BCA Kartu Kredit",
            }
        else:
            return {
                "bank": "BCA",
                "statement_type": "account",
                "display_name": "BCA Rekening",
            }

    # --- OCBC detection ---
    is_ocbc = any(k in text_upper for k in [
        "OCBC", "OCBC NISP", "BANK OCBC",
    ])
    if is_ocbc:
        is_credit_card = any(k in text_upper for k in [
            "KARTU KREDIT", "CREDIT CARD", "KREDIT LIMIT",
        ])
        if is_credit_card:
            return {
                "bank": "OCBC",
                "statement_type": "credit_card",
                "display_name": "OCBC Kartu Kredit",
            }
        return {
            "bank": "OCBC",
            "statement_type": "account",
            "display_name": "OCBC Rekening",
        }

    # --- Marketplace detection ---
    is_tokopedia = any(k in text_upper for k in ["TOKOPEDIA", "TOKOPEDIA SELLER"])
    if is_tokopedia:
        return {
            "bank": "Tokopedia",
            "statement_type": "marketplace",
            "display_name": "Tokopedia",
        }

    is_shopee = any(k in text_upper for k in ["SHOPEE", "SHOPEE SELLER"])
    if is_shopee:
        return {
            "bank": "Shopee",
            "statement_type": "marketplace",
            "display_name": "Shopee",
        }

    return {
        "bank": "unknown",
        "statement_type": "unknown",
        "display_name": "Tidak Dikenal",
    }


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


# ---------------------------------------------------------------------------
# Master parse function — auto-detects and routes to correct parser
# ---------------------------------------------------------------------------

def parse_pdf(pdf_bytes: bytes, password: str = "") -> tuple[pd.DataFrame, dict]:
    """
    Auto-detect the PDF type and parse it with the appropriate parser.

    Returns:
        (DataFrame of transactions, source_info dict)
    """
    full_text = extract_full_text(pdf_bytes, password)
    source_info = detect_source(full_text)

    bank = source_info["bank"]
    stype = source_info["statement_type"]

    if bank == "BCA" and stype == "credit_card":
        df = parse_bca_credit_card(pdf_bytes, password)
    elif bank == "BCA" and stype == "account":
        df = parse_bca_account(pdf_bytes, password)
    elif bank == "OCBC":
        df = parse_ocbc_statement(pdf_bytes, password)
    else:
        # Try BCA credit card as fallback (most common for this POC)
        try:
            df = parse_bca_credit_card(pdf_bytes, password)
            source_info["display_name"] = "Kartu Kredit (terdeteksi)"
        except ValueError:
            raise ValueError(
                f"Tidak bisa mengenali format dokumen ini.\n"
                f"Bank terdeteksi: {source_info['display_name']}\n"
                f"Saat ini mendukung: BCA Kartu Kredit, BCA Rekening, OCBC."
            )

    return df, source_info
