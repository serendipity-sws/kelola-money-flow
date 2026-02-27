"""
llm_parser.py — LLM-based statement parser using Gemini 2.5 Flash

Fallback parser for banks without dedicated regex parsers.
Sends extracted PDF text to Gemini with a structured schema,
validates results against source text, and returns a DataFrame
matching the standard contract.

Uses google-genai SDK with Pydantic response_schema for structured output.
"""

import time
from typing import Literal

import pandas as pd
from pydantic import BaseModel

from google import genai
from google.genai import types

from categories import categorize_transaction, EXPENSE_RULES, CREDIT_RULES
from validation import validate_transactions


# ---------------------------------------------------------------------------
# Pydantic schema for structured Gemini output
# ---------------------------------------------------------------------------

class Transaction(BaseModel):
    date: str                                          # YYYY-MM-DD
    description: str                                   # exact text from PDF
    amount: float                                      # always positive, in IDR
    transaction_type: Literal["expense", "income"]     # expense or income


class StatementData(BaseModel):
    bank_name: str
    statement_type: Literal["credit_card", "account"]
    currency: str                                      # "IDR"
    transactions: list[Transaction]
    statement_period_start: str                         # YYYY-MM-DD
    statement_period_end: str                           # YYYY-MM-DD


# ---------------------------------------------------------------------------
# System prompt for Gemini
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a financial document parser. Extract ALL individual transactions from this Indonesian bank statement.

RULES:
1. Amounts must be EXACT — copy the number from the text. Always positive. In IDR (no decimals).
2. Charges/purchases/debits = "expense". Payments/credits (CR) = "income".
3. SKIP summary lines: TOTAL, SUBTOTAL, SALDO, SALDO SEBELUMNYA, LAST MONTH'S BALANCE, RINGKASAN, TAGIHAN BULAN INI, PEMBAYARAN MINIMUM, BIAYA ADMIN summary rows.
4. DO include individual fee lines (BIAYA NOTIFIKASI, STAMP DUTY, etc.) as expense transactions.
5. Copy descriptions EXACTLY as written — do not modify, translate, or summarize.
6. Indonesian number format: dots = thousands separator (1.500.000 = 1500000), commas can also be thousands separator (1,500,000 = 1500000).
7. Date format output: YYYY-MM-DD. Resolve year from the statement header/period.
8. If a transaction has CR or is explicitly a payment/credit, it is "income". Everything else is "expense".
9. bank_name should be the bank brand (e.g., "BCA", "OCBC", "BNI", "Mandiri", "CIMB Niaga").
10. statement_type: "credit_card" if it's a credit card statement, "account" if savings/checking."""


# ---------------------------------------------------------------------------
# Main LLM parse function
# ---------------------------------------------------------------------------

def llm_parse_statement(
    full_text: str,
    api_key: str,
    max_retries: int = 1,
) -> tuple[pd.DataFrame, dict]:
    """
    Parse a bank statement using Gemini 2.5 Flash.

    Args:
        full_text: Extracted text from PDF (all pages concatenated)
        api_key: Gemini API key
        max_retries: Number of retries on API error

    Returns:
        (DataFrame matching standard contract, source_info dict with bank_name/statement_type)

    Raises:
        ValueError: If no valid transactions found or API fails
    """
    if not api_key:
        raise ValueError(
            "Gemini API key belum dikonfigurasi.\n"
            "Tambahkan GEMINI_API_KEY di Settings → Secrets pada Streamlit Cloud,\n"
            "atau di .streamlit/secrets.toml untuk development lokal."
        )

    client = genai.Client(api_key=api_key)

    # Build the prompt with the statement text
    user_prompt = f"Extract all transactions from this bank statement:\n\n{full_text}"

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=StatementData,
                    temperature=0.0,
                ),
            )

            # Parse the structured response
            statement = StatementData.model_validate_json(response.text)
            break

        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(2 ** attempt)  # exponential backoff: 1s, 2s
                continue
            raise ValueError(f"AI parsing gagal setelah {max_retries + 1} percobaan: {last_error}")

    if not statement.transactions:
        raise ValueError("AI tidak menemukan transaksi dalam dokumen ini.")

    # Validate transactions against source text
    raw_transactions = [tx.model_dump() for tx in statement.transactions]
    valid_transactions, rejected_count = validate_transactions(raw_transactions, full_text)

    if not valid_transactions:
        raise ValueError(
            f"AI menemukan {len(raw_transactions)} transaksi, "
            f"tapi semua gagal validasi. Dokumen mungkin tidak didukung."
        )

    # Build DataFrame matching the standard contract
    rows = []
    for tx in valid_transactions:
        amount = tx["amount"]
        tx_type = tx["transaction_type"]

        if tx_type == "income":
            category = categorize_transaction(tx["description"], CREDIT_RULES, fallback="Pembayaran Kartu")
        else:
            category = categorize_transaction(tx["description"], EXPENSE_RULES)
            amount = -amount  # Expenses are negative per contract

        rows.append({
            "date": pd.to_datetime(tx["date"]),
            "description": tx["description"],
            "amount": amount,
            "transaction_type": tx_type,
            "category": category,
            "card": "",  # LLM parser doesn't track card sections
        })

    df = pd.DataFrame(rows)
    df["source"] = f"{statement.bank_name} ({statement.statement_type.replace('_', ' ').title()})"
    df = df.sort_values("date").reset_index(drop=True)

    source_info = {
        "bank_name": statement.bank_name,
        "statement_type": statement.statement_type,
        "parse_method": "llm",
        "total_found": len(raw_transactions),
        "total_valid": len(valid_transactions),
        "rejected": rejected_count,
    }

    return df, source_info
