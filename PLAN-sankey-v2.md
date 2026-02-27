# Kelola: Bidirectional Sankey + Income Visualization

## Context
Current Sankey is expense-only: [Account] → [Expense Categories]. User needs full money flow: income sources → accounts → expense categories. This is a "dangerous" change because it modifies core visualization assumptions. Approach: build new alongside old, swap after proven.

## Target Visualization

```
INFLOW (left)              CENTER              OUTFLOW (right)
─────────────              ──────              ───────────────
Gaji/Salary ──────┐                    ┌────── Makanan & Minuman
                  ├──→ BCA Rekening ──→├────── Transportasi
Freelance ────────┘        │           ├────── Langganan Software
                           │           └────── Belanja Online
Transfer In ──────→ OCBC Kartu Kredit →─────── Cicilan
                           │
Manual/Cash ──────→ Kas/Tunai ────────→─────── Rumah Tangga
```

Income sources (left) → Accounts (center) → Expense categories (right).
Accounts act as pass-through nodes. Width of links = amount.

## Approach: Build Alongside, Then Swap

### Phase 1: `build_sankey_v2()` in charts.py (~2 hours)
**DO NOT touch `build_sankey()`.** Build the new function below it.

New function signature:
```python
def build_sankey_v2(dataframe, payment_categories=None) -> go.Figure | None:
    """
    Bidirectional Sankey: Income Sources → Accounts → Expense Categories.
    Replaces build_sankey() once proven stable.
    """
```

Node layout (3 columns):
- Left nodes: income source categories (from ACCOUNT_RULES + new income categories)
- Center nodes: account/source names (BCA Kartu Kredit, OCBC Kartu Kredit, etc.)
- Right nodes: expense categories (existing from EXPENSE_RULES)

Links:
- Left → Center: income transactions grouped by (category, source), summed
- Center → Right: expense transactions grouped by (source, category), summed

Color scheme:
- Income nodes: green tones (#4a7c59 range, fits YNAB theme)
- Account nodes: existing tan (#c4a882)
- Expense nodes: existing red (#c0504a)
- Income links: green with transparency
- Expense links: existing red with transparency

Edge cases to handle:
- Credit card payments (PAYMENT_CATEGORIES) — exclude from both sides, they're internal transfers
- Transactions with no clear income source — group under "Lainnya" (Other)
- Accounts with only expenses (credit cards with no payments in period) — still show, just no left links

### Phase 2: Waterfall chart function (~1 hour)
New function in charts.py:
```python
def build_waterfall(dataframe, payment_categories=None) -> go.Figure | None:
    """
    Waterfall chart: Starting balance → income adds → expense subtracts → ending balance.
    Alternative view to Sankey for users who think in balance terms.
    """
```
Pure addition — new function, no existing code touched.

### Phase 3: Manual income input (~1 hour)
New section in app.py for manually adding income entries (salary, cash, etc.) that don't come from parsed PDFs.

Manual entries stored in session_state, merged into all_transactions DataFrame.
Same contract: date, description, amount (positive), transaction_type="income", category, source="Manual".

UI: simple form — date picker, description text, amount number input, category dropdown.

### Phase 4: Wire into app.py (~30 min)
- Replace `build_sankey()` call with `build_sankey_v2()` call
- Add view toggle: "Sankey" | "Waterfall" (st.radio or st.tabs)
- Keep `build_sankey()` in charts.py as fallback — delete only after 2+ sessions of stable v2
- Update summary metrics to properly separate real income vs card payments vs transfers

### Phase 5: Update categories.py (~30 min)
Add income categories for bank account statements:
- Ensure ACCOUNT_RULES covers common income sources
- Add income-specific categories if needed: "Pendapatan Usaha", "Investasi", etc.
- These feed the left side of the Sankey

## Modified Files
- `charts.py` — ADD `build_sankey_v2()` and `build_waterfall()`. DO NOT modify `build_sankey()`
- `app.py` — ADD manual income section, ADD view toggle, SWAP sankey call (one line change)
- `categories.py` — ADD income categories if needed

## Files Unchanged
- `parser.py` — already handles income/expense transaction types
- `styles.py` — pure CSS
- `llm_parser.py` / `validation.py` — independent of visualization

## DataFrame Contract Impact
No changes to existing columns. Manual income entries use existing schema:
```python
{"date": datetime, "description": "Gaji Januari", "amount": 15000000.0,
 "transaction_type": "income", "category": "Gaji & Tunjangan",
 "card": "", "source": "Manual"}
```

## Risk Mitigation
- `build_sankey()` stays intact throughout — instant rollback by reverting one call in app.py
- Git commit before starting Phase 4 (the swap)
- Test with existing BCA+OCBC data first (should look identical on expense side)
- Test with manual income entries
- Test with mixed (parsed expenses + manual income)

## Implementation Order
Do Universal Parser (PLAN-universal-parser.md) FIRST. That gives you more bank data to test the bidirectional Sankey with. Building a bidirectional Sankey with only credit card data is pointless — you need bank account statements (with income) to see the left side work.

## Verification
1. Existing BCA+OCBC credit card data → v2 Sankey should look identical to v1 on expense side (no income data from CC statements)
2. Add manual income entries → left side of Sankey populates correctly
3. Toggle to waterfall → shows income/expense as adds/subtracts
4. Revert to `build_sankey()` → old view still works (rollback test)
5. All tabs, metrics, filters work regardless of which Sankey version is active
