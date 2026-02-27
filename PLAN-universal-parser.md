# Kelola: Universal Parser — Hybrid (Regex + LLM Fallback)

## Context
Current parser uses hardcoded regex per bank (~636 lines). Only supports BCA CC, BCA Account, OCBC CC. If user uploads BNI, CIMB, Mandiri — app crashes. If any bank changes PDF format, regex breaks silently. User wants robustness and universal bank support.

**Solution**: Keep proven regex for BCA/OCBC (free, instant, 100% accurate). Add Gemini 2.5 Flash LLM as fallback for any unknown bank. Both paths produce the same DataFrame → same UI. Zero cost (Gemini free tier: 250 req/day).

## Architecture

```
parse_pdf()
    │
    ├─ detect_source() → known bank (BCA/OCBC)?
    │       │
    │       YES → existing regex parser (instant, free)
    │       │
    │       NO → llm_parse_statement()
    │               │
    │               Gemini 2.5 Flash + Pydantic schema
    │               │
    │               validate_transactions() ← amount-in-text check
    │               │
    │               categorize_transaction() ← reuse categories.py
    │
    └─ Both paths → DataFrame [date, description, amount, transaction_type, category, source]
                  → app.py renders same UI regardless of parse method
```

## New Files

### `llm_parser.py` (~130 lines)
- **Pydantic schema** — `Transaction` and `StatementData` models for structured output
- **System prompt** — instruct Gemini to extract transactions, handle IDR formats, skip summary lines
- **`llm_parse_statement(full_text, api_key)`** — send text to Gemini, get structured response, validate, build DataFrame
- **Retry logic** — 1 retry on API error with backoff
- Uses `google-genai` SDK with `response_schema=StatementData` for native Pydantic support

**Pydantic schema:**
```python
class Transaction(BaseModel):
    date: str           # YYYY-MM-DD
    description: str    # exact text from PDF
    amount: float       # always positive, in IDR
    transaction_type: Literal["expense", "income"]

class StatementData(BaseModel):
    bank_name: str
    statement_type: Literal["credit_card", "account"]
    currency: str       # "IDR"
    transactions: list[Transaction]
    statement_period_start: str  # YYYY-MM-DD
    statement_period_end: str    # YYYY-MM-DD
```

**Key prompt rules:**
1. Amounts must be exact — copy from text, always positive, IDR (no decimals)
2. Charges/purchases/debits = "expense", payments/credits (CR) = "income"
3. Skip summary lines (TOTAL, SUBTOTAL, SALDO, etc.)
4. Copy descriptions exactly as written — do not modify or summarize
5. Indonesian format: dots = thousands separator (1.500.000 = 1500000)

### `validation.py` (~60 lines)
- **`validate_transactions(transactions, full_text)`** — verify LLM output against source
  - Amount-in-text check: convert amount to possible IDR formats, verify it appears in original text
  - Date validation: parseable YYYY-MM-DD, reasonable range (not year 1900)
  - Sanity bounds: 0 < amount < 1,000,000,000 IDR
  - Returns only validated transactions + count of rejected ones
- **`amount_to_text_formats(amount)`** — helper: 1500000 → ["1.500.000", "1,500,000", "1500000"]

## Pre-work: Split parser.py (do this FIRST)

parser.py at 636 lines has three distinct reasons to change: adding new bank parsers, fixing existing bank parsers, and changing detection logic. Split before adding more complexity.

Target structure:
```
parser_core.py      Detection logic (detect_source), PDF utilities (decrypt, extract text, parse_idr_amount, format_idr)
parser_bca.py       BCA CC + BCA Account parsers (regex patterns, skip patterns, parse functions)
parser_ocbc.py      OCBC parser (regex patterns, skip patterns, parse function)
parser.py           Thin router: parse_pdf() calls detect_source() then delegates to correct parser module
```

Why now: the Universal Parser adds a fourth parsing path (LLM). Adding it to a 636-line file makes the problem worse. Splitting first means `llm_parser.py` is just another parser module alongside `parser_bca.py` and `parser_ocbc.py` — clean and consistent.

Verification after split: upload BCA + OCBC PDFs, confirm identical results to pre-split. Git commit before AND after.

## Modified Files

### `parser.py` — becomes thin router (~50 lines)
In `parse_pdf()`, replace the current fallback:
```python
# BEFORE (crashes on unknown bank):
else:
    try:
        df = parse_bca_credit_card(pdf_bytes, password)  # blind fallback
    except ValueError:
        raise ValueError("Tidak bisa mengenali format...")

# AFTER (LLM fallback):
else:
    try:
        from llm_parser import llm_parse_statement
        import streamlit as st
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        df, llm_source = llm_parse_statement(full_text, api_key)
        source_info["bank"] = llm_source["bank_name"]
        source_info["statement_type"] = llm_source["statement_type"]
        source_info["display_name"] = f"{llm_source['bank_name']} (AI)"
        source_info["parse_method"] = "llm"
    except Exception as exc:
        raise ValueError(
            f"Tidak bisa mengenali format dokumen ini.\n"
            f"AI parsing gagal: {exc}"
        )
```

### `app.py` — small additions (~15 lines)
- Add "AI" badge next to source when `parse_method == "llm"` (transparency for user)
- Add subtle warning: "Parsed by AI — please verify amounts" for LLM-parsed files
- If no API key configured and unknown bank uploaded, show helpful message with setup instructions

### `requirements.txt`
- Add `google-genai>=1.0.0`

### `.gitignore`
- Add `.streamlit/secrets.toml` (already gitignored via `.streamlit/` or add explicitly)

## API Key Setup

**You (developer) hold one key. End users never see it — zero friction.**

**Getting the key (1 minute):**
1. Go to https://aistudio.google.com/apikey
2. Click "Create API key" → copy it

**Local development:**
```toml
# .streamlit/secrets.toml (gitignored)
GEMINI_API_KEY = "your-key-here"
```

**Streamlit Cloud (deployed app):**
1. Go to app dashboard → Settings → Secrets
2. Add: `GEMINI_API_KEY = "your-key-here"`

**Rate limiting:** None for now. Gemini free tier = 250 req/day, more than enough for friend testing. Add limits later if the app goes wider.

## LLM Accuracy Safeguards

| Risk | Mitigation |
|------|-----------|
| Hallucinated amount | Amount-in-text validation: reject if number not found in source PDF |
| Missed transactions | Show count in UI — user can compare with their statement |
| Wrong expense/income | Check CR/DB markers in nearby text |
| Year wrong | Cross-check against statement period dates |
| API unavailable | Graceful error: "AI parsing unavailable, try again later" |
| No API key | Clear message: "Set up Gemini API key to parse this bank" |

## Implementation Steps

| # | Task | Est. |
|---|------|------|
| 0a | Split parser.py → parser_core.py, parser_bca.py, parser_ocbc.py, thin parser.py router | 30 min |
| 0b | Verify split: upload BCA + OCBC PDFs, confirm identical output. Git commit | 10 min |
| 0c | Create `tests/test_parsers.py` — regression tests for BCA + OCBC (known PDF → expected DataFrame output) | 20 min |
| 1 | Create `llm_parser.py` — Pydantic schema + Gemini call + DataFrame construction | 30 min |
| 2 | Create `validation.py` — amount-in-text check + date + sanity bounds | 20 min |
| 3 | Modify `parser.py` router — add LLM fallback branch | 10 min |
| 4 | Update `requirements.txt` — add `google-genai` | 2 min |
| 5 | Modify `app.py` — AI badge, warning for LLM-parsed, API key error message | 15 min |
| 6 | Run regression tests — confirm BCA/OCBC regex paths unchanged | 5 min |
| 7 | Test with a different bank's PDF — confirm LLM path works | 10 min |
| 8 | Git commit + push + redeploy | 5 min |

**Total: ~2.5 hours** (extra hour for split + tests, but pays for itself immediately)

## New Files
- `parser_core.py` — detection + PDF utilities extracted from parser.py
- `parser_bca.py` — BCA CC + Account parsers extracted from parser.py
- `parser_ocbc.py` — OCBC parser extracted from parser.py
- `tests/test_parsers.py` — regression tests: known PDF → expected DataFrame

## Files Unchanged
- `categories.py` — LLM path reuses same categorization rules
- `charts.py` — visualization independent of parse method
- `styles.py` — pure CSS

## Verification
1. Upload BCA PDF → should use regex path (instant, no API call), same results as before
2. Upload OCBC PDF → should use regex path (instant), same results as before
3. Upload BNI/CIMB/Mandiri PDF → should use LLM path (2-3 sec), show "AI" badge, transactions display correctly
4. Upload BNI PDF with no API key configured → should show helpful error message, not crash
5. Confirm Sankey, metrics, and all tabs work identically regardless of parse method

## Future: Switching to Full LLM
If LLM proves reliable over time, change `parse_pdf()` routing to send ALL banks through `llm_parse_statement()`. One `if` statement change. The hybrid architecture makes this migration trivial.
