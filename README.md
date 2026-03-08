# YourStake Holdings Extraction Pipeline

**Data Engineer Take-Home — Nikita Ravi**

## Overview

This project extracts structured investment holdings from a Fidelity brokerage
statement.

The input consists of **61 CSV tables** produced by parsing the PDF statement.
The pipeline automatically identifies which tables contain holdings data and
extracts the securities into a clean output dataset.

```text
PDF Statement
│
▼
CSV Tables (61)
│
▼
Table Classification
│
▼
Holdings Extraction
│
▼
Clean Portfolio Dataset
```

## Results

- Total CSV tables scanned: **61**
- Holdings tables detected: **12**
- Final holdings extracted: **34**
- Accounts detected: **3**

**Account totals (computed from extraction):**
- General Investments #111-111111 → $108,051.18
- Traditional IRA #222-222222 → $142,413.12
- Education 529 #333-333333 → $28,457.90

*(All market values verified precisely against PDF)*

## Holdings Detection Logic

A table is classified as a holdings table if it contains:

- `Description`
- `Quantity`
- `Ending Market Value` or `Ending Value`

Tables are excluded if they contain signals of activity data such as:

- `Settlement Date`
- `Transaction Description`
- `Post Date`

Rows are filtered to remove:

- subtotal rows (Description starts with "Total")
- category headers (missing Quantity)

## Design Decisions

- **No table IDs are hardcoded.**
- **Tables are detected dynamically based on column signatures.** 
- **Account ownership is inferred from section boundaries.**
- **The pipeline is robust to minor layout variations in Fidelity statements.**

## Run the Pipeline

```bash
pip install -r requirements.txt
python run_pipeline.py
```

Output is saved to `data/output/output_holdings.csv`

To run the unit tests measuring components of the pipeline:

```bash
python run_pipeline.py --test
```
