"""
parser_core.py — Shared utilities for PDF parsing

Contains:
- Indonesian month map
- PDF encryption/decryption helpers
- Text extraction
- IDR amount parsing and formatting
- Bank/statement auto-detection (detect_source)
"""

import io
import re
from datetime import datetime

import pdfplumber
import pikepdf


# ---------------------------------------------------------------------------
# Indonesian month abbreviation map (BCA uses abbreviated months like JAN, FEB, etc.)
# ---------------------------------------------------------------------------

INDO_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MEI": 5, "MAY": 5,
    "JUN": 6, "JUL": 7, "AGU": 8, "AGT": 8, "AUG": 8, "SEP": 9,
    "OKT": 10, "OCT": 10, "NOV": 11, "NOP": 11, "DES": 12, "DEC": 12,
}


# ---------------------------------------------------------------------------
# PDF Utilities
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
