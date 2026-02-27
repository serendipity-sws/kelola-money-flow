"""
parser.py — PDF parsing router and public API

All statements are parsed by Gemini 2.5 Flash LLM. detect_source() is
used only for UI labeling (bank name badge), not for routing.

Regex parsers (parser_bca.py, parser_ocbc.py) are archived in the repo
as fallback — to re-enable for a specific bank, add a routing condition
in parse_pdf() before the LLM call.

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


# ---------------------------------------------------------------------------
# Master parse function — all statements go through LLM
# ---------------------------------------------------------------------------

def parse_pdf(pdf_bytes: bytes, password: str = "") -> tuple[pd.DataFrame, dict]:
    """
    Extract text from PDF, detect bank for labeling, parse via Gemini LLM.

    Returns:
        (DataFrame of transactions, source_info dict)
    """
    full_text = extract_full_text(pdf_bytes, password)
    source_info = detect_source(full_text)

    df, source_info = _llm_parse(full_text, source_info)

    return df, source_info


def _llm_parse(full_text: str, source_info: dict) -> tuple[pd.DataFrame, dict]:
    """Parse statement text using Gemini 2.5 Flash."""
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
