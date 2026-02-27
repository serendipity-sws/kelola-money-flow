"""
categories.py — Category definitions and transaction categorization

Data-driven keyword matching: each rule set is a list of dicts with
"category" and "keywords". First match wins (order matters).
"""

# ---------------------------------------------------------------------------
# Payment categories — CC balance settlements, NOT real spending or income
# ---------------------------------------------------------------------------

PAYMENT_CATEGORIES = {"Pembayaran Kartu", "Refund"}

# Sankey exclusions — internal money movements that inflate the diagram
# Includes PAYMENT_CATEGORIES + bank-account equivalents (transfers, CC bill payments)
SANKEY_EXCLUDED_CATEGORIES = PAYMENT_CATEGORIES | {"Transfer", "Pembayaran"}


# ---------------------------------------------------------------------------
# Credit card expense rules (order matters — first match wins)
# "grab food" must match before "grab", "shopee food" before "shopee"
# ---------------------------------------------------------------------------

EXPENSE_RULES = [
    {"category": "Cicilan",
     "keywords": ["cicilan", "installment"]},

    # Software subscriptions — split from old "Langganan & Telko"
    {"category": "Langganan Software",
     "keywords": ["spotify", "netflix", "youtube premium", "google one",
                  "apple.com", "icloud", "canva", "notion", "chatgpt",
                  "disney", "hbo", "vidio", "prime video"]},

    # Telecom — split from old "Langganan & Telko"
    {"category": "Telekomunikasi",
     "keywords": ["xl", "telkomsel", "indosat", "tri ", "by.u", "atpy",
                  "smartfren"]},

    # Food & Beverage — "grab food" before "grab" in Transportasi
    {"category": "Makanan & Minuman",
     "keywords": ["grab food", "gofood", "shopee food", "mcd", "starbucks",
                  "kfc", "pizza", "burger", "restaurant", "resto", "cafe",
                  "kopi", "hokben", "yoshinoya", "chatime", "mixue", "jco",
                  "breadtalk", "solaria", "warteg", "bakmi", "sate",
                  "martabak", "nasi"]},

    # Transportation — must come AFTER F&B so "grab food" matches first
    {"category": "Transportasi",
     "keywords": ["grab", "gojek", "uber", "taxi", "toll", "transjakarta",
                  "mrt ", "lrt ", "kereta", "parkir", "pertamina", "shell",
                  "bp ", "bluebird", "maxim"]},

    # Online shopping — "shopee food" already matched above
    {"category": "Belanja Online",
     "keywords": ["tokopedia", "shopee", "lazada", "blibli", "amazon",
                  "tiktok shop", "zalora"]},

    {"category": "Elektronik",
     "keywords": ["ibox", "erafone", "electronic", "digimap"]},

    {"category": "Rumah Tangga",
     "keywords": ["ace ", "ikea", "informa", "ruparupa"]},

    {"category": "Kesehatan",
     "keywords": ["apotek", "pharmacy", "dokter", "hospital", "rs ",
                  "klinik", "clinic", "halodoc", "kimia farma", "century"]},

    {"category": "Hiburan",
     "keywords": ["cinema", "bioskop", "cgv", "xxi", "tix", "tiket",
                  "ticket"]},

    {"category": "Transfer & E-Wallet",
     "keywords": ["gopay", "ovo", "dana ", "linkaja", "transfer", "flip",
                  "shopeepay"]},

    {"category": "Asuransi",
     "keywords": ["asuransi", "insurance", "bpjs"]},

    {"category": "Pendidikan",
     "keywords": ["kursus", "course", "udemy", "skillshare", "sekolah",
                  "universitas"]},
]


# ---------------------------------------------------------------------------
# Credit card income/credit rules
# ---------------------------------------------------------------------------

CREDIT_RULES = [
    {"category": "Refund",
     "keywords": ["refund", "reversal", "pengembalian"]},

    {"category": "Pembayaran Kartu",
     "keywords": ["pembayaran", "payment", "mybca"]},
]


# ---------------------------------------------------------------------------
# Bank account transaction rules
# ---------------------------------------------------------------------------

ACCOUNT_RULES = [
    {"category": "Gaji & Tunjangan",
     "keywords": ["gaji", "salary", "thr", "bonus"]},

    {"category": "Bunga",
     "keywords": ["bunga", "interest"]},

    {"category": "Transfer",
     "keywords": ["transfer", "trf", "dari ", "ke "]},

    {"category": "Tarik Tunai",
     "keywords": ["atm", "tarik tunai", "withdrawal"]},

    {"category": "Biaya Admin",
     "keywords": ["biaya admin", "biaya adm", "fee"]},

    {"category": "Pajak",
     "keywords": ["pajak", "tax"]},

    {"category": "Pembayaran",
     "keywords": ["payment", "pembayaran", "bayar"]},

    {"category": "Auto-Debit",
     "keywords": ["debit", "autopay"]},
]


# ---------------------------------------------------------------------------
# Aggregate lists for UI dropdowns
# ---------------------------------------------------------------------------

ALL_EXPENSE_CATEGORIES = [r["category"] for r in EXPENSE_RULES] + ["Pengeluaran Lain"]
ALL_CREDIT_CATEGORIES = [r["category"] for r in CREDIT_RULES] + ["Pembayaran Kartu"]
ALL_ACCOUNT_CATEGORIES = [r["category"] for r in ACCOUNT_RULES] + ["Pendapatan Lain", "Pengeluaran Lain"]
ALL_CATEGORIES = sorted(set(ALL_EXPENSE_CATEGORIES + ALL_CREDIT_CATEGORIES + ALL_ACCOUNT_CATEGORIES))


# ---------------------------------------------------------------------------
# Categorization function
# ---------------------------------------------------------------------------

def categorize_transaction(description: str, rules: list[dict], fallback: str = "Pengeluaran Lain") -> str:
    """
    Match description against keyword rules, return first matching category.
    Falls back to `fallback` if no rule matches.
    """
    d = description.lower()
    for rule in rules:
        if any(kw in d for kw in rule["keywords"]):
            return rule["category"]
    return fallback
