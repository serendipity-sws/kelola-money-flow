"""
app.py — Money Flow POC
Streamlit UI: drag-and-drop PDFs -> auto-detect -> auto-parse -> Sankey diagram
YNAB-inspired green/earthy design
"""

import streamlit as st
import pandas as pd

from parser import parse_pdf, check_pdf_encrypted, format_idr
from categories import PAYMENT_CATEGORIES, ALL_CATEGORIES
from charts import build_sankey, render_sankey_clean
from styles import get_app_css

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Kelola — Money Flow",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Theme CSS
# ---------------------------------------------------------------------------

st.markdown(get_app_css(), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "all_transactions" not in st.session_state:
    st.session_state.all_transactions = pd.DataFrame()
if "file_results" not in st.session_state:
    st.session_state.file_results = {}  # filename -> {status, source_info, error, count}
if "pending_passwords" not in st.session_state:
    st.session_state.pending_passwords = {}  # filename -> pdf_bytes
if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()
if "parsed_dataframes" not in st.session_state:
    st.session_state.parsed_dataframes = {}  # filename -> DataFrame (cached)
if "unlock_errors" not in st.session_state:
    st.session_state.unlock_errors = {}  # filename -> error message
if "category_overrides" not in st.session_state:
    st.session_state.category_overrides = {}  # (date_str, desc, amount) -> new_category


# ---------------------------------------------------------------------------
# Category override helper
# ---------------------------------------------------------------------------

def apply_category_overrides(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Apply user category overrides from session state."""
    if not st.session_state.category_overrides or dataframe.empty:
        return dataframe
    for idx, row in dataframe.iterrows():
        key = (str(row["date"]), row["description"], row["amount"])
        if key in st.session_state.category_overrides:
            dataframe.loc[idx, "category"] = st.session_state.category_overrides[key]
    return dataframe


def try_unlock_pdf(filename: str):
    """Callback for Buka button — runs BEFORE rerun so session state is fresh."""
    password = st.session_state.get(f"pwd_{filename}", "")
    if not password:
        st.session_state.unlock_errors[filename] = "Password kosong."
        return

    pdf_bytes = st.session_state.pending_passwords.get(filename)
    if not pdf_bytes:
        st.session_state.unlock_errors[filename] = "File tidak ditemukan di memori."
        return

    try:
        df, source_info = parse_pdf(pdf_bytes, password)
        st.session_state.file_results[filename] = {
            "status": "success",
            "source_info": source_info,
            "count": len(df),
            "error": None,
        }
        st.session_state.parsed_dataframes[filename] = df
        del st.session_state.pending_passwords[filename]
        st.session_state.unlock_errors.pop(filename, None)

        # Rebuild all_transactions
        all_frames = list(st.session_state.parsed_dataframes.values())
        st.session_state.all_transactions = pd.concat(all_frames, ignore_index=True)
        st.session_state.all_transactions = st.session_state.all_transactions.sort_values("date").reset_index(drop=True)

    except Exception as exc:
        st.session_state.unlock_errors[filename] = str(exc)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown("""
<div class="nav-bar">
    <div>
        <div class="nav-title">Kelola</div>
        <div class="nav-subtitle">Money Flow Visualizer</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Upload section — multi-file, drag-and-drop
# ---------------------------------------------------------------------------

st.markdown("""
<div style="margin-bottom: 8px;">
    <span style="color: #2d3a2e; font-size: 1rem; font-weight: 600;">
        Upload Dokumen Keuangan
    </span>
    <span style="color: #8a9a7a; font-size: 0.8rem; margin-left: 8px;">
        BCA, OCBC, Tokopedia, Shopee — otomatis terdeteksi
    </span>
</div>
""", unsafe_allow_html=True)

uploaded_files = st.file_uploader(
    "Drop PDF di sini atau klik Browse",
    type="pdf",
    accept_multiple_files=True,
    key="pdf_uploader",
    label_visibility="collapsed",
)


# ---------------------------------------------------------------------------
# Process uploaded files automatically
# ---------------------------------------------------------------------------

def process_file(filename: str, pdf_bytes: bytes, password: str = ""):
    """Process a single PDF file and update session state."""
    try:
        df, source_info = parse_pdf(pdf_bytes, password)
        st.session_state.file_results[filename] = {
            "status": "success",
            "source_info": source_info,
            "count": len(df),
            "error": None,
        }
        st.session_state.parsed_dataframes[filename] = df

        if filename in st.session_state.pending_passwords:
            del st.session_state.pending_passwords[filename]

        st.session_state.processed_files.add(filename)
        return df

    except ValueError as exc:
        error_msg = str(exc)
        if "password" in error_msg.lower():
            st.session_state.pending_passwords[filename] = pdf_bytes
            st.session_state.file_results[filename] = {
                "status": "needs_password",
                "source_info": None,
                "count": 0,
                "error": error_msg,
            }
        else:
            st.session_state.file_results[filename] = {
                "status": "error",
                "source_info": None,
                "count": 0,
                "error": error_msg,
            }
        return None

    except Exception as exc:
        st.session_state.file_results[filename] = {
            "status": "error",
            "source_info": None,
            "count": 0,
            "error": f"Error: {exc}",
        }
        return None


# Auto-process newly uploaded files
if uploaded_files:
    new_files_to_process = []

    for uploaded_file in uploaded_files:
        if uploaded_file.name not in st.session_state.processed_files:
            new_files_to_process.append(uploaded_file)

    if new_files_to_process:
        with st.spinner("Menganalisis dokumen..."):
            for uploaded_file in new_files_to_process:
                pdf_bytes = uploaded_file.read()

                is_encrypted = check_pdf_encrypted(pdf_bytes)
                if is_encrypted:
                    st.session_state.pending_passwords[uploaded_file.name] = pdf_bytes
                    st.session_state.file_results[uploaded_file.name] = {
                        "status": "needs_password",
                        "source_info": None,
                        "count": 0,
                        "error": "PDF dilindungi password",
                    }
                    st.session_state.processed_files.add(uploaded_file.name)
                else:
                    process_file(uploaded_file.name, pdf_bytes)

    # Rebuild all_transactions from cached DataFrames
    if st.session_state.parsed_dataframes:
        all_frames = list(st.session_state.parsed_dataframes.values())
        st.session_state.all_transactions = pd.concat(all_frames, ignore_index=True)
        st.session_state.all_transactions = st.session_state.all_transactions.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Show file results & password prompts
# ---------------------------------------------------------------------------

if st.session_state.file_results:
    for filename, result in st.session_state.file_results.items():
        if result["status"] == "success":
            source_name = result["source_info"]["display_name"]
            count = result["count"]
            is_llm = result["source_info"].get("parse_method") == "llm"
            ai_badge = ' <span class="source-badge" style="background:#e8d5b7;color:#8b6914;">AI</span>' if is_llm else ""
            llm_stats = ""
            if is_llm and "llm_stats" in result["source_info"]:
                stats = result["source_info"]["llm_stats"]
                if stats["rejected"] > 0:
                    llm_stats = f' <span style="color:#b8860b;font-size:0.75rem;">({stats["rejected"]} gagal validasi)</span>'
            st.markdown(
                f'<div class="file-item">'
                f'  <div>'
                f'    <div class="file-name">{filename}</div>'
                f'    <span class="source-badge">{source_name}</span>{ai_badge}'
                f'    <span class="file-status success">{count} transaksi ditemukan</span>{llm_stats}'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if is_llm:
                st.caption("Diproses oleh AI — harap periksa kesesuaian nominal.")

        elif result["status"] == "needs_password":
            st.markdown(
                f'<div class="password-section">'
                f'  <span class="password-icon">🔒</span>'
                f'  <strong>{filename}</strong> — PDF ini dilindungi password'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.text_input(
                "Password",
                type="password",
                key=f"pwd_{filename}",
                placeholder="Masukkan password lalu tekan Enter atau klik Buka",
                label_visibility="collapsed",
            )
            st.button(
                "Buka 🔓",
                key=f"unlock_{filename}",
                on_click=try_unlock_pdf,
                args=(filename,),
            )
            if filename in st.session_state.unlock_errors:
                st.error(st.session_state.unlock_errors[filename])

        elif result["status"] == "error":
            st.markdown(
                f'<div class="file-item">'
                f'  <div>'
                f'    <div class="file-name">{filename}</div>'
                f'    <span class="file-status error">{result["error"]}</span>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Empty state — no data yet
# ---------------------------------------------------------------------------

if st.session_state.all_transactions.empty:
    st.markdown("""
    <div class="empty-state">
        <div class="empty-state-icon">📄</div>
        <div class="empty-state-text">
            Drop file PDF rekening koran atau kartu kredit di atas.<br>
            Dokumen akan dikenali dan dianalisis otomatis.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ---------------------------------------------------------------------------
# Data loaded — dashboard
# ---------------------------------------------------------------------------

df = st.session_state.all_transactions.copy()
df = apply_category_overrides(df)

# --- Filter bar ---
st.markdown('<div class="section-title">Filter</div>', unsafe_allow_html=True)
filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 1])

with filter_col1:
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()
    date_range = st.date_input(
        "Rentang Tanggal",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY",
    )

with filter_col2:
    all_categories_in_data = ["Semua"] + sorted(df["category"].unique().tolist())
    selected_category = st.selectbox("Kategori", all_categories_in_data)

with filter_col3:
    min_amount = st.number_input(
        "Min. Nominal (Rp)",
        min_value=0,
        value=0,
        step=100_000,
        format="%d",
    )

# Apply filters
if len(date_range) == 2:
    start_date, end_date = date_range
    df = df[(df["date"].dt.date >= start_date) & (df["date"].dt.date <= end_date)]

if selected_category != "Semua":
    df = df[df["category"] == selected_category]

if min_amount > 0:
    df = df[df["amount"].abs() >= min_amount]


# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------

expense_df = df[df["transaction_type"] == "expense"]
income_df = df[df["transaction_type"] == "income"]

real_income_df = income_df[~income_df["category"].isin(PAYMENT_CATEGORIES)]
card_payment_df = income_df[income_df["category"].isin(PAYMENT_CATEGORIES)]

total_expense = expense_df["amount"].abs().sum()
total_real_income = real_income_df["amount"].sum()
total_card_payments = card_payment_df["amount"].sum()
net_flow = total_real_income - total_expense

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Total Pengeluaran</div>
        <div class="metric-value expense">{format_idr(total_expense)}</div>
    </div>
    """, unsafe_allow_html=True)

with m2:
    if total_card_payments > 0:
        m2_label = "Pembayaran Kartu"
        m2_value = format_idr(total_card_payments)
    else:
        m2_label = "Total Pemasukan"
        m2_value = format_idr(total_real_income)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{m2_label}</div>
        <div class="metric-value">{m2_value}</div>
    </div>
    """, unsafe_allow_html=True)

with m3:
    if total_real_income > 0:
        net_class = "positive" if net_flow >= 0 else "negative"
        m3_label = "Arus Bersih"
        m3_display = format_idr(net_flow)
    else:
        net_class = ""
        m3_label = "Pemasukan Lain"
        m3_display = format_idr(0)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{m3_label}</div>
        <div class="metric-value {net_class}">{m3_display}</div>
    </div>
    """, unsafe_allow_html=True)

with m4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Transaksi</div>
        <div class="metric-value">{len(df)}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sankey diagram
# ---------------------------------------------------------------------------

st.markdown('<div class="section-card">', unsafe_allow_html=True)
sankey_fig = build_sankey(df)

if sankey_fig:
    render_sankey_clean(sankey_fig, height=540)
else:
    st.markdown(
        '<div class="alert-info">Tidak ada data yang cukup untuk diagram Sankey dengan filter ini.</div>',
        unsafe_allow_html=True,
    )
st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Transaction tables
# ---------------------------------------------------------------------------

income_tab_label = "Pemasukan" if total_real_income > 0 else "Pembayaran Kartu"
tab_all, tab_income, tab_expense = st.tabs(["Semua Transaksi", income_tab_label, "Pengeluaran per Kategori"])

with tab_all:
    if df.empty:
        st.info("Tidak ada transaksi.")
    else:
        display_df = df.copy()
        display_df["Tanggal"] = display_df["date"].dt.strftime("%d/%m/%Y")
        display_df["Nominal"] = display_df["amount"].apply(format_idr)
        display_df["Tipe"] = display_df["transaction_type"].map({
            "income": "Masuk",
            "expense": "Keluar",
            "transfer": "Transfer",
        })
        display_df = display_df.rename(columns={
            "description": "Keterangan",
            "category": "Kategori",
            "source": "Sumber",
        })

        # Editable table — only Kategori column is editable (dropdown)
        edited_df = st.data_editor(
            display_df[["Tanggal", "Keterangan", "Nominal", "Tipe", "Kategori", "Sumber"]],
            use_container_width=True,
            hide_index=True,
            disabled=["Tanggal", "Keterangan", "Nominal", "Tipe", "Sumber"],
            column_config={
                "Kategori": st.column_config.SelectboxColumn(
                    "Kategori",
                    options=ALL_CATEGORIES,
                    required=True,
                ),
            },
            key="transaction_editor",
        )

        # Detect category changes and store overrides
        original_categories = display_df["Kategori"].reset_index(drop=True)
        edited_categories = edited_df["Kategori"].reset_index(drop=True)

        if not original_categories.equals(edited_categories):
            changed_mask = original_categories != edited_categories
            for i in changed_mask[changed_mask].index:
                row = df.iloc[i]
                key = (str(row["date"]), row["description"], row["amount"])
                st.session_state.category_overrides[key] = edited_categories[i]
            st.rerun()

with tab_income:
    if income_df.empty:
        st.info("Tidak ada data pemasukan.")
    else:
        inc_summary = (
            income_df.groupby(["category", "source"])["amount"]
            .sum()
            .reset_index()
            .sort_values("amount", ascending=False)
        )
        inc_summary["Total"] = inc_summary["amount"].apply(format_idr)
        inc_summary = inc_summary.rename(columns={"category": "Kategori", "source": "Sumber"})
        st.dataframe(
            inc_summary[["Kategori", "Sumber", "Total"]],
            use_container_width=True,
            hide_index=True,
        )

with tab_expense:
    if expense_df.empty:
        st.info("Tidak ada data pengeluaran.")
    else:
        exp_summary = (
            expense_df.groupby(["category", "source"])["amount"]
            .apply(lambda x: x.abs().sum())
            .reset_index()
            .sort_values("amount", ascending=False)
        )
        exp_summary["Total"] = exp_summary["amount"].apply(format_idr)
        exp_summary = exp_summary.rename(columns={"category": "Kategori", "source": "Sumber"})
        st.dataframe(
            exp_summary[["Kategori", "Sumber", "Total"]],
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown("<div style='height: 32px'></div>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; padding: 16px; color: #8a9a7a; font-size: 0.75rem;">
    Kelola Money Flow · Data bersifat konfidensial · Hanya untuk demo
</div>
""", unsafe_allow_html=True)
