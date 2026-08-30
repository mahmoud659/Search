# ============================================================
# Amazon/parser.py
# أي حاجة بتاخد HTML (string) وتستخرج منه بيانات (سعر، بائع،
# خصم، تقييم...) باستخدام BeautifulSoup بتتحط هنا. مفيش هنا أي
# استدعاء لـ Playwright مباشرة - الملف ده بياخد HTML جاهز بس.
# ============================================================

import re

from bs4 import BeautifulSoup

from .config import AMAZON_DOMAIN
from .utils import clean_text, normalize_digits, parse_price, parse_percentage, extract_shipping


# ============================================================
# DISCOUNT / SALE PRICE
# ============================================================

def find_first_price(elements):
    for element in elements:
        text = clean_text(element.get_text(" ", strip=True))
        if not text:
            continue
        price = parse_price(text)
        if price is not None:
            return price
    return None


def extract_discount_data(container):
    current_price = None
    original_price = None
    discount_percent = None

    current_selectors = [
        ".priceToPay .a-offscreen",
        ".a-price:not(.a-text-price) .a-offscreen",
        ".aod-price .a-offscreen",
        "#corePrice_feature_div .a-offscreen",
        ".a-price-whole",
        ".olpOfferPrice",
    ]

    for selector in current_selectors:
        try:
            elements = container.select(selector)
        except Exception:
            elements = []

        filtered = []
        for element in elements:
            classes = " ".join(element.get("class", []))
            if "a-text-price" in classes:
                continue
            filtered.append(element)

        current_price = find_first_price(filtered)
        if current_price is not None:
            break

    original_selectors = [
        ".a-text-price .a-offscreen",
        ".a-text-price",
        ".a-price[data-a-strike='true'] .a-offscreen",
        "[data-a-strike='true'] .a-offscreen",
        "[class*='strike'] .a-offscreen",
        "[class*='was'] .a-offscreen",
    ]

    for selector in original_selectors:
        try:
            elements = container.select(selector)
        except Exception:
            elements = []
        original_price = find_first_price(elements)
        if original_price is not None:
            break

    discount_selectors = [
        ".savingsPercentage",
        ".a-size-large.savingsPercentage",
        "[class*='savingsPercentage']",
        "[class*='discount']",
    ]

    for selector in discount_selectors:
        try:
            elements = container.select(selector)
        except Exception:
            elements = []
        for element in elements:
            text = clean_text(element.get_text(" ", strip=True))
            if not text:
                continue
            discount_percent = parse_percentage(text)
            if discount_percent is not None:
                break
        if discount_percent is not None:
            break

    full_text = normalize_digits(clean_text(container.get_text(" ")) or "")
    if discount_percent is None:
        discount_percent = parse_percentage(full_text)

    if current_price is not None and original_price is not None and original_price > current_price:
        inferred = (original_price - current_price) / original_price * 100
        if discount_percent is None:
            discount_percent = inferred

    return {
        "current_price": round(current_price, 2) if current_price is not None else None,
        "original_price": round(original_price, 2) if original_price is not None else None,
        "discount_percent": round(discount_percent, 2) if discount_percent is not None else None,
    }


# ============================================================
# SELLER
# ============================================================

def extract_seller_url(container, base_url):
    from urllib.parse import urljoin

    selectors = [
        'a[href*="seller="]', 'a[href*="/sp?"]',
        '#aod-offer-soldBy a', '#sellerProfileTriggerId',
    ]
    for selector in selectors:
        try:
            element = container.select_one(selector)
        except Exception:
            element = None
        if not element:
            continue
        href = element.get("href")
        if href:
            return urljoin(base_url, href)
    return None


def extract_seller_name(container):
    selectors = [
        "#aod-offer-soldBy a", "#aod-offer-soldBy", ".olpSellerName",
        "[id*='soldBy'] a", "[id*='soldBy']", ".aod-seller-name",
        "a[href*='seller=']",
    ]
    for selector in selectors:
        try:
            element = container.select_one(selector)
        except Exception:
            element = None
        if not element:
            continue
        seller = clean_text(element.get_text(" ", strip=True))
        if seller:
            return seller
    return None


# ============================================================
# SHIPPING FROM AOD
# ============================================================

def extract_offer_shipping(container):
    selectors = [
        "#aod-offer-shipping", ".aod-delivery-promise",
        ".olpShippingLabel", "[class*='shipping']", "[class*='delivery']",
    ]
    for selector in selectors:
        try:
            elements = container.select(selector)
        except Exception:
            elements = []
        for element in elements:
            text = clean_text(element.get_text(" ", strip=True))
            if not text:
                continue
            return extract_shipping(text)
    return extract_shipping(container.get_text(" ", strip=True))


# ============================================================
# CONDITION / FULFILLMENT / RATINGS
# ============================================================

def extract_condition(text):
    if not text:
        return "New"
    lowered = text.lower()
    if "مستعمل" in lowered or "used" in lowered:
        return "Used"
    if "مجدد" in lowered or "renewed" in lowered:
        return "Renewed"
    return "New"


def extract_fulfillment(text):
    if not text:
        return "Seller"
    amazon_words = [
        "Amazon.sa", "Amazon", "الشحن من قبل Amazon",
        "التوصيل بواسطة Amazon", "Fulfilled by Amazon", "Ships from Amazon",
    ]
    lowered = text.lower()
    for word in amazon_words:
        if word.lower() in lowered:
            return "Amazon.sa"
    return "Seller"


def extract_seller_rating(text):
    if not text:
        return None
    patterns = [
        r"(\d+(?:\.\d+)?)\s*(?:من|out of)\s*5",
        r"(\d+(?:\.\d+)?)\s*/\s*5",
        r"Seller Rating\s*[:\-]?\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*نجوم",
    ]
    text = normalize_digits(text)
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                value = float(match.group(1))
                if 0 <= value <= 5:
                    return value
            except ValueError:
                pass
    return None


def extract_seller_reviews(text):
    if not text:
        return None
    text = normalize_digits(text)
    patterns = [
        r"\(([\d,]+)\s*ratings?\)",
        r"التقييمات\s*([\d,]+)",
        r"([\d,]+)\s*تقييم",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1).replace(",", ""))
            except ValueError:
                pass
    return None


def extract_positive_rating(text):
    if not text:
        return None
    text = normalize_digits(text)
    patterns = [
        # سمحنا بكلمة زيادة بين النسبة والكلمة المفتاحية
        # (زي "92% تقييمات إيجابية" مش بس "92% إيجابية")
        r"(\d+)\s*%[^\d%]{0,20}?إيجابية",
        r"(\d+)\s*%[^\d%]{0,20}?positive",
        r"(\d+)\s*%[^\d%]{0,20}?موجب",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
    return None


# ============================================================
# PARSE AOD OFFER
# ============================================================

def extract_star_rating_from_classes(soup_or_tag):
    """
    أمازون أحيانًا بتشفّر عدد النجوم جوه اسم كلاس CSS
    (زي "a-star-4-5" يعني 4.5 نجمة) بدل النص الظاهر. الطريقة دي
    أدق وأوثق من قراءة النص لأنها رقم صريح في الكود، مش تخمين
    من نص متجاور ممكن يكون غير مرتبط.
    """
    try:
        elements = soup_or_tag.select("[class]")
    except Exception:
        return None

    for el in elements:
        classes = el.get("class") or []
        class_str = " ".join(classes)
        if "a-star" not in class_str:
            continue
        m = re.search(r"a-star(?:-mini)?-(\d)(?:-(\d))?\b", class_str)
        if m:
            whole = int(m.group(1))
            frac = m.group(2)
            rating = whole + (int(frac) / 10 if frac else 0)
            if 0 <= rating <= 5:
                return rating
    return None


def get_seller_info_scope(soup):
    """
    نضيّق النطاق لنص العنصر اللي فيه اسم البائع + أقرب 2 عنصر شقيق بعده
    (مش أب العنصر كله، اللي غالبًا بيحتوي السعر والشحن كمان ويسبب لخبطة).
    """
    seller_selectors = [
        "#aod-offer-soldBy", ".olpSellerName", "[id*='soldBy']",
        "a[href*='seller=']",
    ]
    for selector in seller_selectors:
        try:
            element = soup.select_one(selector)
        except Exception:
            element = None
        if not element:
            continue

        own_text = clean_text(element.get_text(" ", strip=True)) or ""

        # دايمًا نضيف نص أقرب 2 عنصر شقيق بعده (مش أب العنصر كله)
        # عشان نلحق التقييم لو كان في سطر/عنصر منفصل جنب اسم البائع
        extra_parts = [own_text]
        sibling = element.find_next_sibling()
        count = 0
        while sibling is not None and count < 2:
            sib_text = clean_text(sibling.get_text(" ", strip=True))
            if sib_text:
                extra_parts.append(sib_text)
            sibling = sibling.find_next_sibling()
            count += 1

        combined = " ".join(p for p in extra_parts if p)
        return combined or None

    return None


def parse_aod_offer(html, index):
    soup = BeautifulSoup(html, "html.parser")
    text = clean_text(soup.get_text(" ", strip=True))
    if not text:
        return None

    seller = extract_seller_name(soup)
    discount_data = extract_discount_data(soup)
    price = discount_data["current_price"]

    if not seller:
        return None
    if price is None:
        return None

    shipping = extract_offer_shipping(soup)
    total = round(price + shipping, 2)
    original_price = discount_data["original_price"]
    discount_percent = discount_data["discount_percent"]

    discount_amount = None
    if original_price is not None and price is not None and original_price > price:
        discount_amount = round(original_price - price, 2)

    # نستخرج التقييم من نطاق ضيق (جنب اسم البائع) بدل الكارت كله
    seller_scope_text = get_seller_info_scope(soup)
    rating_source = seller_scope_text if seller_scope_text else text

    # نجرب الطريقة الأدق الأول (كلاس CSS)، ولو مفيش نرجع لقراءة النص
    seller_rating = extract_star_rating_from_classes(soup)
    if seller_rating is None:
        seller_rating = extract_seller_rating(rating_source)

    return {
        "offer_id": f"AOD-{index:04d}",
        "offer_type": "OTHER_AMAZON_SELLER",
        "seller": seller,
        "seller_url": extract_seller_url(soup, AMAZON_DOMAIN),
        "price": round(price, 2),
        "original_price": original_price,
        "discount_amount": discount_amount,
        "discount_percent": discount_percent,
        "shipping": round(shipping, 2),
        "total": total,
        "currency": "SAR",
        "condition": extract_condition(text),
        "fulfillment": extract_fulfillment(text),
        "seller_rating": seller_rating,
        "seller_reviews": extract_seller_reviews(rating_source),
        "positive_rating": extract_positive_rating(rating_source),
    }


def extract_aod_offers_from_snapshots(snapshots):
    print(f"\n[+] AOD snapshots to parse: {len(snapshots)}")
    offers = []
    for index, html in enumerate(snapshots, 1):
        offer = parse_aod_offer(html, index)
        if not offer:
            print(f"[!] Could not parse AOD snapshot #{index}")
            continue
        offers.append(offer)
    return offers


# ============================================================
# CURRENT OFFER
# ============================================================

def parse_current_offer(html_candidates, page_url):
    """
    بياخد قائمة outerHTML للحاويات المرشحة (من browser.py) وبيرجع
    أول عرض حالي (buybox) قدر يستخرج منه سعر فعلي.
    """
    print("\n[+] Searching for CURRENT OFFER...")

    for html in html_candidates:
        soup = BeautifulSoup(html, "html.parser")
        text = clean_text(soup.get_text(" ", strip=True))
        if not text:
            continue

        discount_data = extract_discount_data(soup)
        price = discount_data["current_price"]
        if price is None:
            continue

        seller_selectors = [
            "#sellerProfileTriggerId", "#merchant-info a", "#merchant-info",
            "[data-csa-c-slot-id*='merchant'] a", ".tabular-buybox-text",
        ]
        seller = None
        for selector in seller_selectors:
            try:
                element = soup.select_one(selector)
            except Exception:
                element = None
            if element:
                seller = clean_text(element.get_text(" ", strip=True))
                if seller:
                    break
        if not seller:
            seller = "Amazon.sa"

        shipping = 0.0
        shipping_selectors = [
            "#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE",
            "#deliveryBlockMessage", "#delivery-message", "[data-csa-c-delivery-time]",
        ]
        for selector in shipping_selectors:
            try:
                element = soup.select_one(selector)
            except Exception:
                element = None
            if element:
                shipping_text = clean_text(element.get_text(" ", strip=True))
                if shipping_text:
                    shipping = extract_shipping(shipping_text)
                    break

        total = round(price + shipping, 2)
        original_price = discount_data["original_price"]
        discount_percent = discount_data["discount_percent"]

        discount_amount = None
        if original_price is not None and original_price > price:
            discount_amount = round(original_price - price, 2)

        offer = {
            "offer_id": "CURRENT-0001",
            "offer_type": "CURRENT_OFFER",
            "seller": seller,
            "seller_url": extract_seller_url(soup, page_url),
            "price": round(price, 2),
            "original_price": original_price,
            "discount_amount": discount_amount,
            "discount_percent": discount_percent,
            "shipping": round(shipping, 2),
            "total": total,
            "currency": "SAR",
            "condition": "New",
            "fulfillment": extract_fulfillment(text),
            "seller_rating": extract_seller_rating(text),
            "seller_reviews": extract_seller_reviews(text),
            "positive_rating": extract_positive_rating(text),
        }

        print("[+] CURRENT OFFER detected:")
        print(f"    Seller: {seller}")
        print(f"    Actual price: {price:.2f} SAR")
        if original_price is not None:
            print(f"    Original price: {original_price:.2f} SAR")
        if discount_percent is not None:
            print(f"    Discount: {discount_percent:.2f}%")
        print(f"    Shipping: {shipping:.2f} SAR")
        print(f"    Total: {total:.2f} SAR")

        return offer

    print("[!] CURRENT OFFER could not be identified.")
    return None


# ============================================================
# CURRENT vs AOD
# ============================================================

def is_same_offer(current, aod):
    if not current or not aod:
        return False

    current_url = current.get("seller_url")
    aod_url = aod.get("seller_url")

    if (current_url and aod_url and current_url == aod_url
            and current.get("price") == aod.get("price")
            and current.get("shipping") == aod.get("shipping")):
        return True

    if (current.get("seller") == aod.get("seller")
            and current.get("price") == aod.get("price")
            and current.get("shipping") == aod.get("shipping")
            and current.get("original_price") == aod.get("original_price")):
        return True

    return False


def build_final_offers(current_offer, aod_offers):
    final = []
    if current_offer:
        final.append(current_offer)

    for offer in aod_offers:
        if current_offer and is_same_offer(current_offer, offer):
            print("[+] AOD offer matches CURRENT offer; excluding only this AOD/current duplicate.")
            continue
        final.append(offer)

    return final
