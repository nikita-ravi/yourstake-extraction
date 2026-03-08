import re

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
