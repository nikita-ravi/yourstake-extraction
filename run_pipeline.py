import sys
import pandas as pd
from src.pipeline import run_pipeline, validate
from src.utils import clean_num
from src.parsing import parse_security
from src.detection import classify_table

CSV_DIR = "data/input"
OUTPUT_FILE = "data/output/output_holdings.csv"

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
