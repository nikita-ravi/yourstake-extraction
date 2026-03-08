# YourStake Data Engineer Take-Home: Written Responses
### Nikita Ravi | March 2026

---

## 1. What validation checks can you run to ensure everything is extracted correctly?

I implemented six levels of validation in `extract_holdings.py`, and all pass:

**Check 1 — Market value totals match statement summaries (the gold standard)**

The statement's "Total Holdings" rows serve as ground truth. After extraction, I sum the `Market Value` column per account and compare to the statement total. All three accounts check out to the cent:
- General Investments `111-111111`: **$108,051.18** ✅
- Traditional IRA `222-222222`: **$142,413.12** ✅
- 529 Plan `333-333333`: **$28,457.90** ✅

**Check 2 — No holdings with a missing Market Value**

Every extracted row must have a non-null, numeric market value. Any row without one would indicate a failed parse and is flagged as a hard failure.

**Check 3 — Every exchange-traded security has a Symbol or CUSIP**

Stocks, ETFs, bonds, and money market funds must have an identifier. The only expected exceptions are LP partnership interests and 529 mutual funds (which have no exchange ticker) — these are flagged informatively, not as failures.

**Check 4 — Short positions flagged for awareness**

Negative quantities are valid (ESGR appears as a short position in the statement) but unusual enough to warrant explicit awareness reporting rather than silent acceptance.

**Check 5 — No duplicate Symbol/CUSIP within the same account**

A ticker shouldn't appear twice in the same account for the same security type. The same CUSIP appearing across different accounts (e.g., the same bond held in both accounts) is valid and expected.

**Additional checks I would add with more time:**
- **Row-level math check**: verify `abs(Quantity × Price Per Unit - Market Value) < $0.01` for every security where a price is available — this catches extraction errors that the aggregate sum check would miss
- **Portfolio total cross-check**: verify that the sum of all three account ending values matches the overall portfolio total (`$274,222.20`, from the statement summary)
- **CUSIP format validation**: confirm all CUSIP identifiers match the standard 9-character alphanumeric pattern
- **Unreasonable cost basis flags**: if `Cost Basis` is more than 10× `Market Value` (or vice versa), flag for human review as a potential parsing error

---

## 2. How might you extract the information from the PDF (into CSVs or otherwise)?

The 61 CSVs in the take-home represent what a PDF table extraction tool would produce. In production, I would choose a tool based on the PDF's structure:

**For well-formatted, digitally-generated PDFs like Fidelity statements:**

1. **`pdfplumber`** — My first choice for tabular data in Python. It uses precise character-level positioning to reconstruct tables, handling merged cells and multi-line rows better than most alternatives. It's pure Python with no Java dependency.

2. **`camelot`** (lattice + stream modes) — Excellent when tables have visible grid lines (lattice mode). Fidelity statements mix bordered and borderless tables, so I'd use lattice mode for bordered sections and stream mode for the others.

3. **AWS Textract** — For production at scale, especially when statements arrive from many different custodians with varied formatting, Textract's "Analyze Document" API with table detection is robust. It handles scanned (image-based) PDFs, not just text-layer PDFs. Given that YourStake already uses AWS, this aligns naturally with existing infrastructure.

**My end-to-end extraction workflow:**
```
PDF
  → pdfplumber.extract_tables() → raw table list per page
  → classify each table by header signature
      ("Description, Quantity, Price, Ending Market Value" → holdings table)
      ("Settlement Date, Security Name, Transaction Description" → transactions table)
  → apply targeted parser per table type
  → validate outputs
  → merge into final holdings CSV
```

**The trickiest part** is handling multi-row bond entries — some bonds span two rows where the second row contains rating/insurance metadata (e.g., "Fixed Coupon; MBIA Insured; Moodys BAA1"). My approach is to require a parseable numeric `Quantity` to accept a row as a security entry; rows without a quantity are treated as continuations and skipped.

---

## 3. What about this task was challenging? What approaches did you try on your path to your ultimate solution?

**The core challenge: 61 tables, no single schema**

The CSVs span the entire statement — holdings, transaction histories, daily balance ledgers, income summaries, credit card activity, legal disclosures, and more. There is no single extraction rule. Correctly identifying *which* tables contain investment holdings required reading the full statement structure carefully before writing a single line of code.

**Challenges and how I approached them:**

**1. Mapping tables to accounts — without hardcoding.**
I first scanned every CSV's column headers to build a mental map of the statement. Rather than hardcoding "table 13 = Account 111," I built dynamic detection: the script auto-finds the account index table (by looking for columns containing "Page" and "Account Number"), then finds account section boundaries (tables containing "Beginning Account Value"), and maps holdings tables to accounts by section ordering. This revealed that only 12 out of 61 tables are holdings — everything else (transactions, disclosures, etc.) is auto-excluded.

**2. Three different security identifier patterns.**
- Stocks and ETFs: ticker in parentheses → `APPLE INC (AAPL)`
- Bonds: CUSIP after literal "CUSIP:" → `SABRATEK CORP NT CV CUSIP: 78571UAA6`
- LP interests and 529 funds: no identifier at all → `ADI NET LEASE INC & GROWTH LP...`

Getting one regex to handle all three cleanly without false positives took iteration. The key insight: Fidelity is remarkably consistent — tickers are always in parentheses, CUSIPs always follow the literal string "CUSIP:".

**3. OCR artifacts in security names.**
Several names had a stray `M ` prefix (e.g., "M CITIGROUP INC", "M VENTAS INC"). This is a margin indicator from the PDF's visual layout — not part of the actual security name. I stripped it with a targeted rule: if a name begins with `M ` and the remaining text is substantial, remove the prefix.

**4. The ENSTAR short position.**
ESGR appears with `-100.00` shares — a short position that was transferred out per the statement's transfer activity section. The negative quantity and negative market value are correct and intentional. I preserve the data faithfully and surface it in validation (Check 4) rather than silently dropping or filtering it.

**5. Subtotal/category header rows mixed into data rows.**
Holdings tables intermix section header rows ("Common Stocks", "Corporate Bonds") and subtotal rows ("Total Stocks — 32% of account") with actual security rows. I filtered these by requiring both a non-empty description that doesn't start with "Total" and a parseable numeric quantity.

---

## 4. With more time, what would you improve about your solution?

**1. Row-level validation: Quantity × Price = Market Value**

This is the most powerful single-row sanity check and catches errors that the aggregate sum misses. If `abs(Quantity × Price - Market Value) > $0.01`, the row is flagged for review. My current solution validates at the account level (sum of market values) but not at the individual row level.

**2. Confidence scoring for ambiguous securities**

LP interests, warrants, and bonds with complex multi-line descriptions are harder to parse reliably. I would add a `parse_confidence` column (`HIGH`, `MEDIUM`, `LOW`) so downstream systems and human reviewers know exactly which rows to scrutinize.

**3. Test suite with synthetic statements**

A small set of synthetic Fidelity statements with known correct outputs would make the extractor testable and safe to refactor. This is especially important when onboarding new custodian formats (Schwab, Vanguard, etc. all have their own table layouts).

**4. Handling multiple custodians**

YourStake processes data from many custodians, not just Fidelity. The architecture I'd move toward is a pluggable extractor interface — one class per custodian, each implementing a common `extract_holdings(pdf_path) -> DataFrame` interface — backed by a custodian detection heuristic that identifies the source from the PDF's header or footer.

**5. Incremental updates and change detection**

Production would need to track statement dates, detect holdings that disappeared since last month (potentially sold), and flag market value changes that seem implausible for a single period (data quality signal for bad extraction).

**6. Column name fuzzy matching**

My current solution matches column names with exact substring checks (e.g., "quantity" must appear in the column header). A more robust approach would use fuzzy string matching to handle slight variations across custodians or statement versions (e.g., "Units" instead of "Quantity", "Current Value" instead of "Ending Market Value").

---

*Thank you for this take-home — it was a genuinely interesting problem that reflects real data engineering work I'd be excited to do at YourStake every day.*
