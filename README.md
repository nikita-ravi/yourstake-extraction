# Fidelity Holdings Extractor

**YourStake Data Engineer Take-Home — Nikita Ravi**

---

## Quick Start

```bash
# Install dependency
pip install pandas

# Run extraction
python extract_holdings.py

# Run unit tests
python extract_holdings.py --test

# Run with detailed audit trail
python extract_holdings.py --verbose
```

---

## What This Does

Extracts investment holdings from a Fidelity brokerage statement (pre-parsed into 61 CSVs) and outputs a clean, structured CSV with one row per security.

**Input:** `Fidelity CSVs/` folder containing `fidelity-table-1.csv` through `fidelity-table-61.csv`

**Output:** `output_holdings.csv` with columns:

| Column | Description | Example |
|---|---|---|
| Symbol/CUSIP | Ticker or bond identifier | `AAPL`, `78571UAA6` |
| Name | Security name | `APPLE INC` |
| Quantity | Units held | `25.00` |
| Cost Basis | Original purchase cost | `9350.12` |
| Market Value | Current position value | `13132.75` |
| Account | Account label and number | `GENERAL INVESTMENTS # 111-111111` |

---

## How It Works — Fully Dynamic, Zero Hardcoding

The script does **not** hardcode any table numbers, account names, or security names. It reads the data itself to figure everything out in a **single pass** through all CSV files.

### Pipeline (one pass through all files)

```
For each CSV file:
    ├── Is it the Account Index?      → Extract account names & numbers
    ├── Is it a Section Boundary?     → Mark where each account's data begins
    ├── Is it a Holdings Table?       → Queue for extraction
    └── None of the above?            → Skip
```

### Table Detection Rules

**A table IS a holdings table if its columns contain:**
- `Description` — what asset
- `Quantity` — how many units owned
- `Ending Market Value` / `Ending Value` / `Price` — what it's worth

**A table is NOT a holdings table if its columns contain:**
- `Settlement Date` — indicates trade/transaction history
- `Transaction Description` — indicates activity log
- `Post Date` / `Check Num.` — indicates card/check activity

**Why both rules are needed:** Transaction tables also have Description, Quantity, and Price columns — but they show trades, not current positions. The exclusion rules catch them first.

### Row Filtering (inside each holdings table)

| Keep? | Rule | Example |
|---|---|---|
| ✅ Keep | Has Description + numeric Quantity + not a Total | `APPLE INC (AAPL), qty=25` |
| ❌ Skip | Description starts with "Total" | `Total Stocks (32% of holdings)` |
| ❌ Skip | Quantity is empty | `COMMON STOCK` (category header) |

### Account Assignment

1. **Auto-detect the account index** — scan for a table with `Page` + `Account Number` columns
2. **Auto-detect section boundaries** — scan for tables containing `Beginning Account Value`
3. **Map by position** — holdings tables after boundary N but before boundary N+1 belong to account N

---

## Results

| Account | Holdings | Market Value |
|---|---|---|
| GENERAL INVESTMENTS # 111-111111 | 18 | $108,051.18 |
| PERSONAL RETIREMENT # 222-222222 | 14 | $142,413.12 |
| EDUCATION (529) ACCOUNTS # 333-333333 | 2 | $28,457.90 |
| **Total** | **34** | **$278,922.20** |

All market value totals match the statement's "Total Holdings" rows to the penny. ✅

---

## Unit Tests

27 tests covering all core functions. Run with `python extract_holdings.py --test`:

- **`clean_numeric`** — currency/comma stripping, footnote removal, edge cases
- **`extract_symbol_name`** — ticker parsing, CUSIP parsing, fund family handling
- **`classify_table`** — correctly accepts holdings, rejects transactions and summaries
- **`is_valid_holding_row`** — keeps securities, skips totals and category headers
- **`clean_name`** — OCR artifact removal, category prefix stripping
- **`extract_account_type`** — account label extraction from index

---

## Files

| File | Description |
|---|---|
| `extract_holdings.py` | Extraction pipeline (single-pass, ~530 lines) |
| `output_holdings.csv` | Extracted holdings (34 rows, 3 accounts) |
| `written_responses.md` | Answers to the 4 take-home questions |
| `Fidelity CSVs/` | Source data (61 CSV files from the statement) |
| `sample-output.csv` | Provided sample showing expected output format |
| `sample-new-fidelity-acnt-stmt.pdf` | Original Fidelity statement PDF |

---

## Dependencies

- Python 3.8+
- pandas
