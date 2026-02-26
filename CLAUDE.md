# Money Flow POC

## Project Goal
Parse bank statement PDFs and visualize money flow as an interactive Sankey diagram.
Demo to non-technical stakeholder. Deadline: Friday 7pm.

## Current Status (Session 2 complete)
- parser.py: working — BCA CC (4 tx ✓) AND OCBC CC (43 tx ✓) both tested against real PDFs
- app.py: working — light theme, password unlock flow, metrics, Sankey (account → expense only)
- .streamlit/config.toml: created — fixes all dark widget styling globally
- App runs at localhost:8502 (port 8501 may be occupied from earlier)
- Python 3.14.3 installed at: C:\Users\Stevien Washington\AppData\Local\Programs\Python\Python314\
- End-to-end verified: upload both PDFs, BCA auto-parses, OCBC prompts password, 47 total transactions, Sankey displays

## Outstanding Issue (start here next session)
- **Sankey text rendering**: Plotly renders SVG labels with a white stroke/halo "emboss" effect that looks bad
- User confirmed: "eh you still screwed up the text in the sankey lah"
- `textfont` on the node dict reduces it slightly but does NOT eliminate it — it's baked into Plotly's SVG engine
- **Best fix options** (pick one):
  - (A) Replace `build_sankey()` with `go.Bar` horizontal grouped bar chart — cleaner for non-technical audience, no text rendering issues
  - (B) Hide node labels entirely (`color="rgba(0,0,0,0)"`) and use `fig.add_annotation()` to manually render clean HTML labels at node positions
  - (C) Accept current cosmetic limitation (not recommended for demo)

## Stack
- Python 3.14.3, Streamlit 1.54, pdfplumber, Plotly, pikepdf
- Run app: `streamlit run app.py` (or use full path to streamlit.exe)
- Install deps: `pip install -r requirements.txt`

## Architecture
- `parser.py` — PDF detection + extraction. Auto-detects bank & statement type from text content.
- `app.py` — Streamlit UI. Single-page, no sidebar. Drag-and-drop upload, auto-analyze.
- `.streamlit/config.toml` — Light theme config. Fixes all dark widget styling.

## PDF Formats Confirmed (from real samples)

### BCA Credit Card Statement
- Text-based, NOT table-based (pdfplumber tables only catch summary rows)
- Transaction line format: `DD-MMM DD-MMM DESCRIPTION AMOUNT [CR]`
- Examples: `25-JAN 25-JAN ATPY XL JAN 087809919227 166.500`
- CR suffix = payment/credit, no suffix = charge/expense
- Statement year extracted from header: `TANGGAL REKENING : 25 JANUARI 2026`
- Month abbreviations: JAN, FEB, MAR, APR, MEI, JUN, JUL, AGU/AGT, SEP, OKT, NOV/NOP, DES
- Cards appear as sections: "BCA EVERYDAY CARD", "VISA CARD", etc.
- Cross-year handling: if statement=JAN and transaction=DES → previous year
- Amount format: dot as thousands separator, no decimal (`166.500` = IDR 166,500)

### BCA Account Statement (tabungan/giro)
- Parser written but NOT yet tested against real sample
- Expected format: DD/MM DESCRIPTION AMOUNT DB/CR BALANCE

### OCBC Credit Card Statement ✓ TESTED (43 transactions)
- Text-based PDF, password protected
- Transaction line format: `DD/MM DD/MM DESCRIPTION AMOUNT [CR]`
- Amount format: comma as thousands separator (`39,623,645` = IDR 39,623,645)
- CR suffix = payment/credit, no suffix = charge/expense
- Year extracted from header: `r"Tanggal Cetak Tagihan\s*:\s*\d{2}-\d{2}-(\d{4})"`
- Key regex: `r"^(\d{2})/(\d{2})\s+\d{2}/\d{2}\s+(.+?)\s+([\d,]+)\s*(CR)?$"`
- Skip lines containing: LAST MONTH, SUBTOTAL, TOTAL, RINGKASAN, BIAYA, STAMP DUTY, STATEMNT, INFORMASI
- Amount parsing: `float(amount_raw.replace(",", ""))` — commas are thousands separators
- Real transactions verified: Google One→Langganan & Telko, Grab→Transportasi, Shopee/Tokopedia→Belanja

## PDF Sources
- BCA credit card statement (tested ✓, 4 transactions)
- OCBC credit card statement (tested ✓, 43 transactions, password: use pikepdf)
- BCA account statement (untested)
- Tokopedia or Shopee seller export report (untested, password protected)

## Key Design Decisions
- Auto-detect source from PDF text content (no user selection needed)
- Password prompt appears ONLY if PDF is encrypted (detected via pikepdf)
- Auto-analyze on file upload (no button click needed)
- Multi-file drag-and-drop upload
- YNAB-inspired UI: earthy greens (#2d5016, #3a6b1e), warm beige (#f5f3ef), brown accents
- `PAYMENT_CATEGORIES = {"Pembayaran Kartu", "Refund"}` — CC balance payments are NOT income, shown as neutral metric
- Sankey shows account → expense only (no income side) — avoids misleading Rp 39M payment dominating chart

## PDF Password Handling
- pikepdf checks encryption before parsing
- Password field only shown for encrypted PDFs
- Password passed directly to pikepdf for decryption
- Never stored anywhere — session only for POC
- **Important pattern**: `st.button(on_click=try_unlock_pdf, args=(filename,))` — user must press Enter in password field first to commit to `st.session_state`, THEN click Buka

## Metrics Section (app.py ~lines 677–731)
Four metric cards:
1. **Total Pengeluaran** — sum of all expense transactions (excludes PAYMENT_CATEGORIES)
2. **Pembayaran Kartu** — sum of PAYMENT_CATEGORIES (neutral, shown separately — these are CC balance settlements)
3. **Pemasukan Lain** — sum of real income (non-payment CR transactions, typically 0 for CC-only statements)
4. **Transaksi** — count of expense transactions only

```python
PAYMENT_CATEGORIES = {"Pembayaran Kartu", "Refund"}
real_income_df = income_df[~income_df["category"].isin(PAYMENT_CATEGORIES)]
card_payment_df = income_df[income_df["category"].isin(PAYMENT_CATEGORIES)]
total_expense = expense_df["amount"].abs().sum()
total_real_income = real_income_df["amount"].sum()
total_card_payments = card_payment_df["amount"].sum()
```

## Sankey Diagram (app.py `build_sankey()`, ~lines 740–841)
- Title: "Arus Pengeluaran"
- Structure: Account nodes (left) → Expense Category nodes (right)
- Excludes PAYMENT_CATEGORIES from both sides
- Node colors: tan `#c4a882` for accounts, warm red `#c0504a` for expense categories
- Link color: `rgba(196, 168, 130, 0.4)` (tan, semi-transparent)
- `textfont=dict(family="Inter, sans-serif", size=13, color="#2d3a2e")` set on node dict
- **Known issue**: Plotly SVG white-stroke halo still visible on labels (see Outstanding Issue above)

```python
expense_rows = dataframe[
    (dataframe["transaction_type"] == "expense") &
    (~dataframe["category"].isin(PAYMENT_CATEGORIES))
]
# account_nodes on left, expense_categories on right
node_colors = (["#c4a882"] * len(account_nodes) + ["#c0504a"] * len(expense_categories))
```

## Tab Labels (app.py ~line 843)
```python
st.tabs(["Semua Transaksi", "Pembayaran Kartu", "Pengeluaran per Kategori"])
```

## UI Theme
- YNAB-inspired green/earthy tones
- Dark green header gradient (#2d5016 → #3a6b1e)
- Warm beige background (#f5f3ef)
- All custom CSS in app.py
- Inter font family
- `.streamlit/config.toml` with `base="light"` fixes ALL dark widget styling (labels, dropdowns, date pickers, number inputs, password inputs)

## CSS Fix for Password Input (app.py)
Streamlit renders password inputs as `type="text"` (NOT `type="password"`), so old CSS selectors never matched. Fix targets the wrapper div:
```css
[data-testid="stTextInputRootElement"] {
    background: #ffffff !important;
    border: 1.5px solid #d5cfc4 !important;
    border-radius: 8px !important;
}
[data-testid="stTextInputRootElement"] > div { background: #ffffff !important; }
[data-testid="stTextInputRootElement"] input {
    background: #ffffff !important;
    color: #2d3a2e !important;
    border: none !important;
}
[data-testid="stTextInputRootElement"] button {
    background: #ffffff !important;
    color: #7a8a6a !important;
    border: none !important;
}
[data-testid="stTextInputRootElement"]:focus-within {
    border-color: #7a9e5a !important;
    box-shadow: 0 0 0 2px rgba(122,158,90,0.2) !important;
}
```

## Code Style
- Functions over classes for this POC
- Explicit variable names, no abbreviations
- Comments on all PDF parsing logic — this will be read again later
- Separate parser.py (data extraction) from app.py (UI) cleanly

## Constraints
- Friday deadline — working and presentable beats elegant and broken
- Single-page Streamlit app, no sidebar
- No authentication layer for POC
- Assume Indonesian locale: IDR currency, DD/MM/YYYY dates
- No LLM needed for parsing — regex is sufficient for these structured PDFs
