import os
import re
import pandas as pd

def discover_tables(folder):
    """Find and sort all fidelity-table-*.csv files."""
    files = {}
    for f in os.listdir(folder):
        m = re.match(r"fidelity-table-(\d+)\.csv", f)
        if m: files[int(m.group(1))] = os.path.join(folder, f)
    return dict(sorted(files.items()))

def read_table(path):
    """Read CSV, using the first row as the header."""
    df = pd.read_csv(path, index_col=0)
    if df.empty: return df
    df.columns = df.iloc[0]
    return df.iloc[1:].reset_index(drop=True)

def clean_num(x):
    """Convert string currency/quantities to clean strings suitable for floats."""
    if pd.isna(x): return ""
    s = re.sub(r"[$,]", "", str(x).strip())
    s = re.sub(r"[A-Za-z]+$", "", s).strip()
    try:
        float(s)
        return s
    except ValueError:
        return ""

def find_col(df, *terms):
    """Find the first column name that contains any of the search terms."""
    cols = {str(c).lower(): c for c in df.columns}
    for term in terms:
        for c_lower, c in cols.items():
            if term in c_lower:
                return c
    return None

def contains_text(df, text):
    """Check if text exists in any column header or cell."""
    text = text.lower()
    if any(text in str(c).lower() for c in df.columns): return True
    for i in range(df.shape[1]):
        for v in df.iloc[:, i]:
            if text in str(v).lower(): return True
    return False
