"""
parser.py — PDF parsing router and public API

Auto-detects bank and statement type from PDF content, then delegates
to the appropriate bank-specific parser module:
  - parser_bca.py  (BCA Credit Card, BCA Account)
  - parser_ocbc.py (OCBC Credit Card)
  - (future) llm_parser.py (unknown banks via Gemini LLM)

Public API used by app.py and charts.py:
  parse_pdf(pdf_bytes, password) -> (DataFrame, source_info)
  check_pdf_encrypted(pdf_bytes) -> bool
  format_idr(amount) -> str
"""

import pandas as pd

# Re-export public API so app.py/charts.py imports stay unchanged
from parser_core import (
    check_pdf_encrypted,
    format_idr,
    extract_full_text,
    detect_source,
)

from parser_bca import parse_bca_credit_card, parse_bca_account
from parser_ocbc import parse_ocbc_statement


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
