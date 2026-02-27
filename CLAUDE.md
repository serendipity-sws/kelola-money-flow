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

## Architecture (modular, flat structure)
```
app.py           (~520 lines)  Streamlit UI, layout, state, event handling
parser.py        (~100 lines)  Thin router: extract text → detect bank → LLM parse
parser_core.py   (~170 lines)  Utilities: encryption, text extraction, IDR formatting, detect_source
parser_bca.py    (~230 lines)  [ARCHIVED] BCA regex parsers — kept as fallback
parser_ocbc.py   (~145 lines)  [ARCHIVED] OCBC regex parser — kept as fallback
llm_parser.py    (~175 lines)  Gemini 2.5 Flash structured output + Pydantic schema
validation.py    (~60 lines)   Amount-in-text anti-hallucination check
categories.py    (~149 lines)  Keyword rules: EXPENSE_RULES, CREDIT_RULES, ACCOUNT_RULES
charts.py        (~245 lines)  Sankey v1 (expense-only) + v2 (bidirectional) + SVG cleanup
styles.py        (~359 lines)  YNAB-inspired CSS theme
```

## Parsing Architecture
All statements go through Gemini 2.5 Flash LLM. detect_source() is used only for UI labeling.
- Credit card statements: CREDIT_RULES for income, EXPENSE_RULES for expenses
- Account statements: ACCOUNT_RULES for both income and expenses
- Validation: amount-in-text check catches hallucinated numbers
- Regex parsers archived in parser_bca.py / parser_ocbc.py as fallback (one-line routing change to re-enable)

## Supported PDF Formats
- **BCA Credit Card** ✓ tested (4 tx) — via LLM
- **OCBC Credit Card** ✓ tested (43 tx) — via LLM, password-protected
- **BCA Account** ✓ tested (33 tx) — via LLM, multi-line format
- **Any other bank** — via LLM (untested, should work)

## Current Status (Session 4 complete)

### Done
- Core architecture: modular, working
- BCA CC + OCBC CC + BCA Account parsing verified (80 total transactions)
- All-LLM parsing via Gemini 2.5 Flash (regex archived as fallback)
- Parser split: parser.py → parser_core, parser_bca, parser_ocbc, llm_parser, validation
- Bidirectional Sankey v2: Income Sources → Accounts → Expense Categories
- Adaptive metrics: labels change based on data type (CC vs account)
- Correct categorization: account income uses ACCOUNT_RULES (not CREDIT_RULES)
- User recategorization via data_editor dropdown
- Sankey SVG text-stroke fix
- Deployed to Streamlit Cloud
- Gemini API key configured (.streamlit/secrets.toml local, Streamlit Cloud secrets)

### Upcoming: Reimbursement Flagging
- Add `reimbursable` boolean column to DataFrame contract (default=False)
- Transaction-level checkboxes in UI, summary/export view
- Small `reimbursement.py` module if logic gets complex

### Upcoming: Waterfall Chart + Manual Income
See `PLAN-sankey-v2.md` Phases 2-3
- Waterfall chart as alternative view to Sankey
- Manual income input for cash/salary not in PDFs

### Deferred
- Regression tests (need test fixture strategy for PDFs with real financial data)
- Delete build_sankey() v1 once v2 proven stable across 2+ sessions

## When Starting a New Session
1. Read this file and any PLAN-*.md files in project root
2. Check if `SESSION-HANDOFF.md` exists — if so, read it for mid-task context
3. Confirm with me what we're working on before writing code

## When Ending a Session
1. Update "Current Status" section above
2. If mid-task: write `SESSION-HANDOFF.md` with state, decisions, and next steps
3. Git commit with descriptive message
