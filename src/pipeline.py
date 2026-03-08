import pandas as pd
import re
from src.utils import discover_tables, read_table, find_col, clean_num
from src.detection import classify_table, get_account_label
from src.parsing import parse_security

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
