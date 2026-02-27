# Kelola — Money Flow & Financial Advocacy Tool

## What This Is
Personal finance tool for Indonesian users. Parses bank statement PDFs, categorizes transactions, visualizes money flow via Sankey diagrams. Currently a Streamlit POC.

## Stack
- Python 3.14.3 (`C:\Users\Stevien Washington\AppData\Local\Programs\Python\Python314\`)
- Streamlit 1.54, pdfplumber, Plotly, pikepdf
- Run: `streamlit run app.py`
- Install: `pip install -r requirements.txt`
- Deployed: https://kelola-money-fl-bgx3y6grjj7zqewy6fjk8z.streamlit.app/
- GitHub: https://github.com/serendipity-sws/kelola-money-flow.git (private)

## Architecture (5 modules, flat structure)
```
app.py          (~400 lines)  Streamlit UI, layout, state, event handling
parser.py       (~636 lines)  PDF detection, decryption, regex parsing per bank
categories.py   (~149 lines)  Keyword rules + categorize_transaction()
charts.py       (~128 lines)  Sankey diagram builder + SVG cleanup renderer
styles.py       (~359 lines)  YNAB-inspired CSS theme
```

## DataFrame Contract (ALL parsers must output this)
```python
columns = ["date", "description", "amount", "transaction_type", "category", "card", "source"]
# date: datetime | amount: float (negative=expense) | transaction_type: "expense"|"income"
# category: from categories.py | source: "BCA Kartu Kredit"|"OCBC Kartu Kredit"|etc.
```
**This contract is sacred.** Any new parser (regex or LLM) must produce this exact schema. The UI doesn't care how data was parsed. When extending the contract (e.g., adding columns), always use default values so existing code keeps working.

## Key Design Decisions (do not change without discussion)
- Auto-detect bank from PDF text content (no user bank selection)
- Password prompt only for encrypted PDFs (pikepdf for decryption)
- Auto-analyze on upload (no "analyze" button)
- PAYMENT_CATEGORIES = {"Pembayaran Kartu", "Refund"} — excluded from expense analysis
- Category overrides stored in session_state keyed by (date, description, amount)
- UI language: Indonesian. Error messages for users: Indonesian. Code/comments: English

## Supported PDF Formats
- **BCA Credit Card** ✓ tested (4 tx) — `DD-MMM DD-MMM DESC AMOUNT [CR]`, dots as thousands sep
- **OCBC Credit Card** ✓ tested (43 tx) — `DD/MM DD/MM DESC AMOUNT [CR]`, commas as thousands sep, password-protected
- **BCA Account** — parser written, untested (no sample PDF)

## Current Status (Session 3 complete)

### Done
- Core architecture: 5 modules, modular, working
- BCA CC + OCBC CC parsing verified (47 total transactions)
- User recategorization via data_editor dropdown
- Sankey SVG text-stroke fix
- Deployed to Streamlit Cloud

### Next: Universal Parser (Hybrid LLM)
See `PLAN-universal-parser.md` for full implementation plan.
- FIRST: split parser.py (636 lines, 3 reasons to change) → parser_core.py, parser_bca.py, parser_ocbc.py, thin parser.py router
- THEN: add Gemini 2.5 Flash LLM fallback for unknown banks as `llm_parser.py`
- Add regression tests: `tests/test_parsers.py` (known PDF → expected DataFrame)
- New files: `parser_core.py`, `parser_bca.py`, `parser_ocbc.py`, `llm_parser.py`, `validation.py`, `tests/test_parsers.py`
- Pre-req: Gemini API key from https://aistudio.google.com/apikey

### Upcoming: Bidirectional Sankey + Income Tracking
See `PLAN-sankey-v2.md` for full implementation plan.
- Upgrade Sankey from expense-only to full inflow/outflow visualization
- Add waterfall chart as alternative view
- Add manual income input for cash/other sources
- IMPORTANT: Build as `build_sankey_v2()` alongside existing function — do NOT rewrite `build_sankey()`. Swap only after v2 is proven. Keep old function as rollback.

### Upcoming: Reimbursement Flagging
- Add `reimbursable` boolean column to DataFrame contract (default=False)
- Transaction-level checkboxes in UI, summary/export view
- Small `reimbursement.py` module if logic gets complex

### Deferred
- BCA account statement testing (need real PDF sample)

## When Starting a New Session
1. Read this file and any PLAN-*.md files in project root
2. Check if `SESSION-HANDOFF.md` exists — if so, read it for mid-task context
3. Confirm with me what we're working on before writing code

## When Ending a Session
1. Update "Current Status" section above
2. If mid-task: write `SESSION-HANDOFF.md` with state, decisions, and next steps
3. Git commit with descriptive message
