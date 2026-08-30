# ============================================================
# Amazon/amazon.py
# نقطة التجميع (orchestrator) بتاعة أمازون: بيفتح المتصفح
# (browser.py)، يستخرج البيانات (parser.py)، يحفظها (excel_writer.py)
# ============================================================

from datetime import datetime

from playwright.sync_api import sync_playwright

from . import browser
from . import parser
from .config import (
    AMAZON_DOMAIN, ASINS, MY_SELLER_NAME, MY_PRICES,
    OUTPUT_JSON_FILE, OUTPUT_EXCEL_FILE, OUTPUT_LAST_DATA_FILE, HEADLESS,
)
from .excel_writer import append_to_json_file, append_to_excel_file, write_last_data_file


# ============================================================
# تبسيط العرض لحقول جدول المقارنة المطلوبة بس
# ============================================================

def slim_offer(offer, asin, product_url, date_str):
    return {
        "asin": asin,
        "product_url": product_url,
        "date": date_str,
        "offer_id": offer.get("offer_id"),
        "seller": offer.get("seller"),
        "product_price": offer.get("price"),
        "original_price": offer.get("original_price"),
        "discount_amount": offer.get("discount_amount"),
        "shipping": offer.get("shipping"),
        "total": offer.get("total"),
        "seller_rating": offer.get("seller_rating"),
    }


# ============================================================
# مقارنة سعرك انت بالمنافسين
# ============================================================

def analyze_my_position(offers, my_price, my_seller_name):
    """
    بيرجع ملخص: ترتيبك، هل فيه حد أرخص منك، وأقرب منافس.
    """
    result = {
        "my_price": my_price,
        "my_seller_name": my_seller_name,
        "my_offer_found_in_list": False,
        "rank_by_price": None,
        "total_offers": len(offers),
        "cheapest_competitor_price": None,
        "cheapest_competitor_seller": None,
        "am_i_cheapest": None,
        "price_gap_vs_cheapest": None,
    }

    if not offers:
        return result

    sorted_offers = sorted(
        offers,
        key=lambda x: x["total"] if x.get("total") is not None else float("inf")
    )

    if my_seller_name:
        for idx, offer in enumerate(sorted_offers, 1):
            if offer.get("seller") and my_seller_name.strip().lower() in offer["seller"].strip().lower():
                result["my_offer_found_in_list"] = True
                result["rank_by_price"] = idx
                break

    competitors = [
        o for o in sorted_offers
        if not (my_seller_name and o.get("seller") and my_seller_name.strip().lower() in o["seller"].strip().lower())
    ]

    if competitors:
        cheapest = competitors[0]
        result["cheapest_competitor_price"] = cheapest.get("total")
        result["cheapest_competitor_seller"] = cheapest.get("seller")

        if my_price is not None and cheapest.get("total") is not None:
            result["am_i_cheapest"] = my_price <= cheapest["total"]
            result["price_gap_vs_cheapest"] = round(my_price - cheapest["total"], 2)

    return result


# ============================================================
# MAIN SCRAPE (لمنتج واحد)
# ============================================================

def scrape_sellers(asin, my_price=None, my_seller_name=None):
    offer_url = f"{AMAZON_DOMAIN}/gp/offer-listing/{asin}?condition=NEW"

    print("=" * 70)
    print("AMAZON CURRENT OFFER + OTHER AMAZON SELLERS")
    print("=" * 70)
    print(f"\n[+] ASIN: {asin}")
    print("[+] Target: CURRENT OFFER + OTHER AMAZON SELLERS (AOD)")
    print(f"[+] URL: {offer_url}")

    current_offer = None
    aod_offers = []
    product_title = product_description = product_image_url = None

    with sync_playwright() as p:
        pw_browser = p.chromium.launch(headless=HEADLESS)
        context = pw_browser.new_context(
            locale="ar-SA", timezone_id="Asia/Riyadh",
            viewport={"width": 1440, "height": 900}
        )
        page = context.new_page()

        print("\n[+] Opening Amazon...")
        try:
            page.goto(offer_url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"[!] Page load warning: {e}")

        page.wait_for_timeout(5000)
        print("[+] Current URL:", page.url)

        # بيانات المنتج الأساسي بس (عنوان + وصف + صورة) - مرة واحدة
        product_title, product_description, product_image_url = browser.extract_product_info(page)
        print(f"[+] Product title: {product_title}")

        current_offer_html = browser.get_current_offer_html_candidates(page)
        current_offer = parser.parse_current_offer(current_offer_html, page.url)

        if browser.wait_for_aod_section(page):
            print("[+] AOD section detected.")
            snapshots = browser.load_all_aod_offers(page)
            aod_offers = parser.extract_aod_offers_from_snapshots(snapshots)
            print(f"\n[+] AOD offers kept: {len(aod_offers)}")
        else:
            print("[!] AOD section not found.")

        pw_browser.close()

    offers = parser.build_final_offers(current_offer, aod_offers)
    offers.sort(key=lambda x: x["total"] if x.get("total") is not None else float("inf"))
    for rank, offer in enumerate(offers, 1):
        offer["rank"] = rank

    current_count = sum(1 for o in offers if o.get("offer_type") == "CURRENT_OFFER")
    aod_count = sum(1 for o in offers if o.get("offer_type") == "OTHER_AMAZON_SELLER")

    print("\n" + "=" * 110)
    print("FINAL AMAZON OFFERS")
    print("=" * 110)
    for offer in offers:
        discount = f" | Discount: {offer['discount_percent']:.2f}%" if offer.get("discount_percent") is not None else ""
        original = f" | Original: {offer['original_price']:.2f} SAR" if offer.get("original_price") is not None else ""
        print(f"{offer['rank']:>3}. [{offer['offer_type']}] {offer['seller']} | "
              f"Product: {offer['price']:.2f} SAR{original}{discount} | "
              f"Shipping: {offer['shipping']:.2f} SAR | TOTAL: {offer['total']:.2f} SAR")
    print("=" * 110)

    my_position = analyze_my_position(offers, my_price, my_seller_name)
    print("\n" + "-" * 70)
    print("MY POSITION ANALYSIS")
    print("-" * 70)
    if my_position["cheapest_competitor_price"] is not None:
        print(f"[+] Cheapest competitor: {my_position['cheapest_competitor_seller']} "
              f"@ {my_position['cheapest_competitor_price']:.2f} SAR")
    if my_price is not None:
        if my_position["am_i_cheapest"] is True:
            print(f"[✓] أنت الأرخص! (سعرك: {my_price:.2f} SAR)")
        elif my_position["am_i_cheapest"] is False:
            print(f"[!] فيه منافس أرخص منك بـ {abs(my_position['price_gap_vs_cheapest']):.2f} SAR "
                  f"(سعرك: {my_price:.2f}, المنافس: {my_position['cheapest_competitor_price']:.2f})")
    else:
        print("[i] محدّدتش my_price في الإعدادات، مش هينفع نحسب فرق السعر.")
    print("-" * 70)

    timestamp_iso = datetime.now().isoformat()
    product_url = f"{AMAZON_DOMAIN}/dp/{asin}"

    slim_offers = [slim_offer(o, asin, product_url, timestamp_iso) for o in offers]

    product_record = {
        "asin": asin,
        "title": product_title,
        "description": product_description,
        "image_url": product_image_url,
        "product_url": product_url,
    }

    # حفظ البيانات:
    #  - JSON + all_offers.xlsx: أرشيف تاريخي (append) لتتبع تغير الأسعار مع الوقت
    #  - last_data.xlsx: آخر تحديث فقط لكل منتج (بيمسح القديم أوتوماتيك) — ده اللي Streamlit بيقرا منه
    append_to_json_file(slim_offers, OUTPUT_JSON_FILE)
    append_to_excel_file(slim_offers, product_record, OUTPUT_EXCEL_FILE, my_seller_name)
    write_last_data_file(slim_offers, product_record, OUTPUT_LAST_DATA_FILE, my_seller_name)

    result = {
        "asin": asin,
        "product_url": product_url,
        "offer_url": offer_url,
        "extracted_at": timestamp_iso,
        "current_offer_count": current_count,
        "other_amazon_sellers_count": aod_count,
        "total_offer_count": len(offers),
        "my_position": my_position,
        "product": product_record,
        "offers": slim_offers,
    }

    print("\n" + "=" * 70)
    print("SCRAPING COMPLETED")
    print("=" * 70)
    print(f"ASIN: {asin}")
    print(f"CURRENT OFFER: {current_count}")
    print(f"OTHER AMAZON SELLERS: {aod_count}")
    print(f"TOTAL OFFERS: {len(offers)}")
    print("=" * 70)

    return result


# ============================================================
# تشغيل كل الـ ASINs في ASINS واحد ورا التاني
# ============================================================

def run_all():
    all_results = []
    for asin in ASINS:
        print(f"\n\n{'#' * 70}\n# TRACKING: {asin}\n{'#' * 70}")
        try:
            result = scrape_sellers(
                asin=asin,
                my_price=MY_PRICES.get(asin),
                my_seller_name=MY_SELLER_NAME,
            )
            all_results.append(result)
        except Exception as e:
            # لو منتج واحد فشل، منكملش نوقف باقي المنتجات
            print(f"[!!!] فشل تتبع {asin}: {e}")
            continue

    return all_results
