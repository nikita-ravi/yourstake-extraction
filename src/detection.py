import re
from src.utils import contains_text

def classify_table(df):
    """Determine if a table is 'account_index', 'section_boundary', 'holdings', or 'other'."""
    cols = {str(c).lower() for c in df.columns}

    # 1. Transaction tables (not holdings)
    bad = {"settlement date", "transaction description", "transaction total", 
           "post date", "check num.", "reference", "payee", 
           "trans. date", "total additions", "total subtractions"}
    if cols & bad: return "other"

    # 2. Account index (defines the accounts)
    if any("page" in c for c in cols) and any("account" in c for c in cols):
        for _, row in df.iterrows():
            for c in df.columns:
                if re.match(r"\d{3}-\d{6}", str(row[c]).strip()): return "account_index"

    # 3. Section boundary (marks start of a new account's data)
    if contains_text(df, "Beginning Account Value") and contains_text(df, "Ending Account Value"):
        return "section_boundary"

    # 4. Holdings criteria
    has_desc = any("description" in c for c in cols)
    has_qty = any("quantity" in c for c in cols)
    
    # Needs a value column, fallback to price
    has_value = any(("ending market value" in c) or ("ending value" in c) for c in cols)
    if not has_value: has_value = any("price" in c for c in cols)

    # Pre-check for summary tables (percent but no quantity)
    if any("percent" in c for c in cols) and not has_qty: return "other"

    if has_desc and has_qty and has_value:
        return "holdings"
        
    return "other"

def get_account_label(label_raw):
    """Extract leading uppercase words as the account type descriptor."""
    words = str(label_raw).split()
    out = []
    for w in words:
        if w.isupper() or (w.startswith("(") and w.endswith(")")): out.append(w)
        else: break
    return " ".join(out) if out else str(label_raw).split(" - ")[0].strip()
