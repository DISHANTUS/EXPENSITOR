"""Receipt OCR-text parsing: get the total right, pull the line items, and
never treat a subtotal or tax line as the total.

Getting the TOTAL wrong is the worst failure — it's the expense amount — so the
total tests come first. The item lines feed per-user price learning, so they
matter next.

The text blocks below are deliberately noisy: real ML Kit output drops currency
markers, misaligns columns and includes header/footer cruft.
"""

from __future__ import annotations

from app.intelligence.companion import receipt_parser as rp

GROCERY = """
FRESH MART SUPERMARKET
123 Main Road, Chennai
GSTIN: 33ABCDE1234F1Z5
------------------------
Milk 1L            58.00
Bread              45.00
Tomatoes 2kg       90.00
Eggs 12            84.00
------------------------
Subtotal          277.00
CGST 2.5%           6.93
SGST 2.5%           6.93
Grand Total       290.86
Paid via UPI
17/07/2026
"""

CAFE = """
CafE Aroma
Table 4
Cappuccino x2      240
Croissant          120
Total              360
Thank you!
"""


def test_the_labelled_total_is_picked_over_the_subtotal():
    out = rp.parse(GROCERY)
    assert out is not None
    # 290.86 (Grand Total), NOT 277.00 (Subtotal) and NOT the biggest item.
    assert out["total"] == "290.86"


def test_a_subtotal_is_never_mistaken_for_the_total():
    out = rp.parse(GROCERY)
    assert out["total"] != "277.00"


def test_line_items_and_their_prices_are_pulled():
    out = rp.parse(GROCERY)
    items = {i["name"]: i["price"] for i in out["items"]}
    assert items.get("Milk 1L") == "58.00"
    assert items.get("Bread") == "45.00"
    assert items.get("Tomatoes 2kg") == "90.00"
    assert items.get("Eggs 12") == "84.00"


def test_tax_and_subtotal_lines_are_not_line_items():
    out = rp.parse(GROCERY)
    names = {i["name"].lower() for i in out["items"]}
    for junk in ("subtotal", "cgst", "sgst", "grand total"):
        assert junk not in names


def test_the_merchant_comes_from_the_top():
    assert rp.parse(GROCERY)["merchant"] == "FRESH MART SUPERMARKET"
    assert rp.parse(CAFE)["merchant"] == "CafE Aroma"


def test_the_date_is_read_when_present():
    assert rp.parse(GROCERY)["date"] == "2026-07-17"


def test_a_receipt_with_no_labelled_total_falls_back_to_the_biggest_amount():
    # CAFE has "Total 360" so it's labelled; test the fallback with a receipt
    # that has priced items but no total line.
    text = "Corner Shop\nPen 20\nNotebook 60\nStapler 150\n"
    out = rp.parse(text)
    assert out is not None
    assert out["total"] == "150"          # largest priced line, user-confirmed
    assert out["item_count"] == 3


def test_random_text_is_not_a_receipt():
    assert rp.parse("hey are we still meeting at 5pm tomorrow?") is None
    assert rp.parse("") is None
    assert rp.parse("   \n  \n ") is None


def test_a_receipt_with_only_a_total_still_parses():
    out = rp.parse("QuickPay\nTotal 500\n")
    assert out is not None and out["total"] == "500"


def test_prices_with_currency_markers_and_commas_parse():
    out = rp.parse("Big Store\nTV Unit    Rs.1,25,000.00\nTotal Rs 1,25,000.00\n")
    # Indian grouping (1,25,000) — commas stripped either way.
    assert out["total"] == "125000.00"
