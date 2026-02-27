"""
parser.py — PDF parsing router and public API

Auto-detects bank and statement type from PDF content, then delegates
to the appropriate bank-specific parser module:
  - parser_bca.py  (BCA Credit Card, BCA Account)
  - parser_ocbc.py (OCBC Credit Card)
  - llm_parser.py  (unknown banks via Gemini 2.5 Flash)

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

    Known banks (BCA, OCBC) use fast regex parsers.
    Unknown banks fall back to Gemini LLM parsing.

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
        # BCA account format is multi-line — regex parser can't handle it,
        # so route through LLM which correctly merges multi-line transactions
        df, source_info = _llm_fallback(full_text, source_info)
    elif bank == "OCBC":
        df = parse_ocbc_statement(pdf_bytes, password)
    else:
        # Unknown bank — try LLM fallback
        df, source_info = _llm_fallback(full_text, source_info)

    return df, source_info


def _llm_fallback(full_text: str, source_info: dict) -> tuple[pd.DataFrame, dict]:
    """Attempt LLM parsing for unrecognized bank statements."""
    try:
        import streamlit as st
        api_key = st.secrets.get("GEMINI_API_KEY", "")
    except Exception:
        api_key = ""

    if not api_key:
        raise ValueError(
            "Tidak bisa mengenali format dokumen ini.\n"
            f"Bank terdeteksi: {source_info['display_name']}\n\n"
            "Untuk parsing otomatis dengan AI, tambahkan GEMINI_API_KEY\n"
            "di Settings → Secrets (Streamlit Cloud) atau .streamlit/secrets.toml."
        )

    from llm_parser import llm_parse_statement

    try:
        df, llm_info = llm_parse_statement(full_text, api_key)
        source_info["bank"] = llm_info["bank_name"]
        source_info["statement_type"] = llm_info["statement_type"]
        source_info["display_name"] = f"{llm_info['bank_name']} (AI)"
        source_info["parse_method"] = "llm"
        source_info["llm_stats"] = {
            "total_found": llm_info["total_found"],
            "total_valid": llm_info["total_valid"],
            "rejected": llm_info["rejected"],
        }
        return df, source_info
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            f"Tidak bisa mengenali format dokumen ini.\n"
            f"AI parsing gagal: {exc}"
        )
