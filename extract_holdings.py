import os
import re
import sys
import pandas as pd

CSV_DIR = "Fidelity CSVs"
OUTPUT_FILE = "output_holdings.csv"

# --- 1. Generic Helpers ---

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


# --- 2. Security Parsing ---

CATEGORY_PREFIXES = (
    "Bond Funds ", "Short-term Funds ", "Common Stocks ", "COMMON STOCK ",
    "Preferred Stocks ", "Corporate Bonds ", "Municipal Bonds ",
    "Other Bonds ", "Asset Backed Securities ", "US Treasury/Agency Securities "
)

def parse_security(desc):
    """Extract symbol/CUSIP and clean name from Fidelity descriptions."""
    desc = str(desc).strip()
    
    # 1. Ticker in parentheses: Apple Inc (AAPL)
    m = re.match(r"^(.*?)\s*\(([A-Z0-9]{1,6})\)\s*.*$", desc)
    if m:
        name = re.split(r"\s+ISIN:", m.group(1))[0].strip()
        return m.group(2), _clean_name(name)

    # 2. CUSIP identifier: SABRATEK CORP CUSIP: 78571UAA6
    m = re.search(r"CUSIP:\s*([A-Z0-9]{9,12})", desc)
    if m:
        name = re.split(r"\s*CUSIP:", desc)[0].strip()
        name = re.sub(r"^(Corporate Bonds|Municipal Bonds|Other Bonds|Asset Backed Securities|US Treasury/Agency Securities)\s+", "", name)
        return m.group(1), _clean_name(name)

    # 3. Fund family in parens (no ticker)
    m = re.match(r"^(.*?)\s*\(Fidelity (?:Funds|Fds)\)", desc, re.IGNORECASE)
    if m:
        return "", _clean_name(m.group(1))

    return "", _clean_name(desc)

def _clean_name(name):
    name = str(name).strip()
    if name.startswith("M ") and len(name) > 2: name = name[2:].strip()
    for p in CATEGORY_PREFIXES:
        if name.startswith(p): return name[len(p):].strip()
    return name


# --- 3. Dynamic Table Classification ---

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


# --- 4. Main Pipeline ---

def run_pipeline(csv_dir, output_file):
    tables = discover_tables(csv_dir)
    
    # State tracking for single pass
    accounts = []
    boundaries = []
    holdings_dfs = []

    # Single Pass: Classify everything
    for tnum, path in tables.items():
        try: df = read_table(path)
        except: continue
        
        kind = classify_table(df)
        if kind == "account_index" and not accounts:
            acct_col = find_col(df, "account number")
            label_col = find_col(df, "account type", "account name")
            for _, row in df.iterrows():
                num = str(row.get(acct_col, "")).strip() if acct_col else ""
                if re.match(r"\d{3}-\d{6}", num):
                    accounts.append({
                        "number": num,
                        "label": str(row.get(label_col, "")).strip() if label_col else ""
                    })
        elif kind == "section_boundary":
            boundaries.append(tnum)
        elif kind == "holdings":
            holdings_dfs.append((tnum, df))

    # Build section-to-account mapping
    account_map = {}
    for i, b_tnum in enumerate(boundaries):
        if i < len(accounts):
            account_map[b_tnum] = f"{get_account_label(accounts[i]['label'])} # {accounts[i]['number']}"
        else:
            account_map[b_tnum] = f"Account {i+1}"

    def assign_account(tnum):
        prior = [s for s in boundaries if s <= tnum]
        return account_map[prior[-1]] if prior else "Unknown Account"

    # Extract holdings
    records = []
    for tnum, df in holdings_dfs:
        acct = assign_account(tnum)
        desc_col = find_col(df, "description")
        qty_col = find_col(df, "quantity")
        mv_col = find_col(df, "ending market value", "ending value")
        cb_col = find_col(df, "total cost basis", "cost basis")

        for _, row in df.iterrows():
            desc = str(row.get(desc_col, "")).strip()
            qty = clean_num(row.get(qty_col, ""))
            if not desc or desc.lower().startswith("total") or not qty:
                continue # Skip totals and category headers

            symbol, name = parse_security(desc)
            cb_raw = str(row.get(cb_col, "")).strip().lower() if cb_col else ""
            cb = clean_num(row[cb_col]) if cb_col and cb_raw not in ("n/a", "unknown", "nan", "-") else ""
            
            records.append({
                "Symbol/CUSIP": symbol, "Name": name, "Quantity": qty,
                "Cost Basis": cb,
                "Market Value": clean_num(row.get(mv_col, "")) if mv_col else "",
                "Account": acct,
            })

    output = pd.DataFrame(records)
    output.to_csv(output_file, index=False)
    
    print(f"Extracted {len(output)} holdings across {output['Account'].nunique()} accounts.")
    return output


# --- 5. Validation & Testing ---

def validate(df):
    """Run data quality checks."""
    print("\n--- Validation ---")
    df["_mv"] = df["Market Value"].apply(lambda x: float(x.replace(",","")) if x else 0.0)
    
    # 1. Total per account
    print("Account Totals:")
    for acct in sorted(df["Account"].unique()):
        print(f"  {acct}: ${df[df['Account']==acct]['_mv'].sum():,.2f}")
    
    # 2. Missing MV
    missing_mv = df[df["_mv"] == 0]
    print(f"\nMissing Market Value: {len(missing_mv)} rows")
    
    # 3. Duplicate Sym/CUSIP per account
    dupes = df[df.duplicated(subset=["Symbol/CUSIP", "Account"], keep=False) & (df["Symbol/CUSIP"] != "")]
    print(f"Duplicate Identifiers: {len(dupes)}")
    
    df.drop(columns=["_mv"], inplace=True)

def run_tests():
    """Basic unit tests for core logic."""
    print("\n--- Running Tests ---")
    
    def assert_test(name, condition):
        print(f"  {'✅' if condition else '❌'} {name}")
        assert condition
        
    assert_test("clean_num handles symbols", clean_num("$1,234.56A") == "1234.56")
    assert_test("clean_num handles N/A", clean_num("N/A") == "")
    
    symbol, name = parse_security("APPLE INC (AAPL)")
    assert_test("parse_security finds ticker", symbol == "AAPL" and "APPLE" in name)
    
    symbol, name = parse_security("SABRATEK CORP CUSIP: 78571UAA6")
    assert_test("parse_security finds CUSIP", symbol == "78571UAA6" and "SABRATEK" in name)
    
    df_txn = pd.DataFrame({"Settlement Date": ["7/11"], "Description": ["X"], "Quantity": [1], "Price": [10]})
    assert_test("classify_table rejects transactions", classify_table(df_txn) == "other")
    
    df_hold = pd.DataFrame({"Description": ["X"], "Quantity": [1], "Ending Value": [10]})
    assert_test("classify_table accepts holdings", classify_table(df_hold) == "holdings")

    print("\nAll tests passed successfully! 🚀")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_tests()
    else:
        df = run_pipeline(CSV_DIR, OUTPUT_FILE)
        validate(df)
