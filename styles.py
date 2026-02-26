"""
styles.py — YNAB-inspired green/earthy theme CSS for Kelola
"""


def get_app_css() -> str:
    """Return the full CSS string for the Streamlit app."""
    return """
<style>
    /* === Base & Typography === */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .stApp {
        background-color: #f5f3ef;
    }

    h1, h2, h3 {
        color: #2d3a2e !important;
    }

    /* === Hide default Streamlit elements === */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }

    /* === Top navigation bar === */
    .nav-bar {
        background: #2d5016;
        background: linear-gradient(135deg, #2d5016 0%, #3a6b1e 100%);
        padding: 16px 32px;
        border-radius: 12px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .nav-title {
        color: #ffffff;
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    .nav-subtitle {
        color: #a8d5a2;
        font-size: 0.85rem;
        font-weight: 400;
    }

    /* === Upload area === */
    .upload-zone {
        background: #ffffff;
        border: 2px dashed #b8c5a3;
        border-radius: 16px;
        padding: 40px 32px;
        text-align: center;
        margin-bottom: 24px;
        transition: all 0.2s ease;
    }
    .upload-zone:hover {
        border-color: #7a9e5a;
        background: #fafdf7;
    }
    .upload-icon {
        font-size: 2.5rem;
        margin-bottom: 8px;
    }
    .upload-text {
        color: #4a5e3a;
        font-size: 1rem;
        font-weight: 500;
    }
    .upload-hint {
        color: #8a9a7a;
        font-size: 0.8rem;
        margin-top: 4px;
    }

    /* === File uploader styling === */
    [data-testid="stFileUploader"] {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }
    [data-testid="stFileUploader"] section {
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }
    [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] {
        background: #ffffff !important;
        border: 2px dashed #b8c5a3 !important;
        border-radius: 12px !important;
        padding: 48px 32px !important;
    }
    [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"]:hover {
        border-color: #7a9e5a !important;
        background: #fafdf7 !important;
    }
    [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] small,
    [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] div {
        color: #4a5e3a !important;
    }
    [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] small {
        color: #7a8a6a !important;
    }
    [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] {
        color: #2d3a2e !important;
    }
    [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] span,
    [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] small,
    [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] div {
        color: #2d3a2e !important;
    }
    [data-testid="stFileUploader"] [data-testid="stFileUploaderFile"] small {
        color: #7a8a6a !important;
    }
    [data-testid="stFileUploader"] li span,
    [data-testid="stFileUploader"] li div,
    [data-testid="stFileUploader"] li small {
        color: #2d3a2e !important;
    }
    [data-testid="stFileUploader"] button {
        background: #3a6b1e !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 8px 20px !important;
        font-weight: 500 !important;
    }
    [data-testid="stFileUploader"] button:hover {
        background: #2d5016 !important;
    }
    [data-testid="stFileUploader"] [data-testid="stFileUploaderDeleteBtn"] {
        background: transparent !important;
        color: #8a9a7a !important;
    }

    /* === Detected source badge === */
    .source-badge {
        display: inline-block;
        background: #e8f0de;
        color: #3a6b1e;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin: 4px 4px 4px 0;
    }
    .source-badge-warn {
        background: #fef3cd;
        color: #856404;
    }

    /* === Metric cards === */
    .metric-card {
        background: #ffffff;
        border: 1px solid #e0ddd5;
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .metric-label {
        color: #7a8a6a;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #2d3a2e;
    }
    .metric-value.income { color: #2d7a1e; }
    .metric-value.expense { color: #b84233; }
    .metric-value.positive { color: #2d7a1e; }
    .metric-value.negative { color: #b84233; }

    /* === Section containers === */
    .section-card {
        background: #ffffff;
        border: 1px solid #e0ddd5;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .section-title {
        color: #2d3a2e;
        font-size: 1rem;
        font-weight: 600;
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 2px solid #e8f0de;
    }

    /* === File list === */
    .file-item {
        background: #fafdf7;
        border: 1px solid #e0ddd5;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .file-name {
        font-weight: 500;
        color: #2d3a2e;
        font-size: 0.9rem;
    }
    .file-status {
        font-size: 0.8rem;
        color: #7a8a6a;
    }
    .file-status.success { color: #2d7a1e; }
    .file-status.error { color: #b84233; }

    /* === Alerts === */
    .alert-success {
        background: #e8f5e2;
        border: 1px solid #b8d4a8;
        border-radius: 10px;
        padding: 12px 16px;
        color: #2d5016;
        font-size: 0.9rem;
        margin-bottom: 16px;
    }
    .alert-error {
        background: #fde8e5;
        border: 1px solid #e8b4ae;
        border-radius: 10px;
        padding: 12px 16px;
        color: #8b2e1f;
        font-size: 0.9rem;
        margin-bottom: 16px;
    }
    .alert-info {
        background: #f0ece4;
        border: 1px solid #d5cfc4;
        border-radius: 10px;
        padding: 12px 16px;
        color: #5a5040;
        font-size: 0.9rem;
        margin-bottom: 16px;
    }

    /* === Password / text input wrapper fix === */
    [data-testid="stTextInputRootElement"] {
        background: #ffffff !important;
        border: 1.5px solid #d5cfc4 !important;
        border-radius: 8px !important;
    }
    [data-testid="stTextInputRootElement"] > div {
        background: #ffffff !important;
    }
    [data-testid="stTextInputRootElement"] input {
        background: #ffffff !important;
        color: #2d3a2e !important;
        border: none !important;
    }
    [data-testid="stTextInputRootElement"] input::placeholder {
        color: #a0a090 !important;
    }
    [data-testid="stTextInputRootElement"] button {
        background: #ffffff !important;
        color: #7a8a6a !important;
        border: none !important;
    }
    [data-testid="stTextInputRootElement"] button svg {
        fill: #7a8a6a !important;
        stroke: #7a8a6a !important;
    }
    [data-testid="stTextInputRootElement"]:focus-within {
        border-color: #7a9e5a !important;
        box-shadow: 0 0 0 2px rgba(122,158,90,0.2) !important;
    }

    /* === Tabs === */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: #f0ece4;
        border-radius: 10px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        font-weight: 500;
        color: #5a5040;
        padding: 8px 20px;
    }
    .stTabs [aria-selected="true"] {
        background: #ffffff !important;
        color: #2d5016 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.08);
    }

    /* === Dataframe styling === */
    [data-testid="stDataFrame"] {
        border-radius: 8px;
        overflow: hidden;
    }

    /* === Sidebar (for filters) === */
    section[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #e0ddd5;
    }

    /* === Plotly chart container === */
    [data-testid="stPlotlyChart"] {
        border-radius: 12px;
        overflow: hidden;
    }

    /* === Password dialog === */
    .password-section {
        background: #fffef5;
        border: 1px solid #e8dca0;
        border-radius: 10px;
        padding: 16px 20px;
        margin: 12px 0;
        color: #2d3a2e !important;
    }
    .password-section strong {
        color: #2d3a2e !important;
    }
    .password-section span {
        color: #5a5040 !important;
    }
    .password-icon {
        font-size: 1.2rem;
        margin-right: 8px;
    }

    /* === Empty state === */
    .empty-state {
        text-align: center;
        padding: 60px 20px;
    }
    .empty-state-icon {
        font-size: 3rem;
        margin-bottom: 12px;
        opacity: 0.7;
    }
    .empty-state-text {
        color: #7a8a6a;
        font-size: 1rem;
    }
</style>
"""
