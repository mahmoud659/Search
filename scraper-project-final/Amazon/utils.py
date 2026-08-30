# ============================================================
# Amazon/utils.py
# دوال مساعدة عامة لتنظيف النصوص والأرقام (مفيش أي Playwright
# أو BeautifulSoup هنا - كلها دوال نصية بسيطة)
# ============================================================

import re


def clean_text(text):
    if not text:
        return None

    text = str(text)

    text = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", text)
    text = " ".join(text.split())

    return text.strip() or None


def normalize_digits(text):
    """
    Converts Arabic/Persian digits to ASCII digits.
    Also normalizes Arabic decimal separators.
    """
    if text is None:
        return ""

    text = str(text)

    translation = str.maketrans(
        "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
        "01234567890123456789"
    )

    text = text.translate(translation)

    text = text.replace("٫", ".")
    text = text.replace("٬", ",")
    text = text.replace("\u00a0", " ")

    return text


def parse_price(text):
    if not text:
        return None

    text = normalize_digits(clean_text(text))
    text = text.replace(",", "")

    match = re.search(r"(\d+(?:\.\d+)?)", text)

    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_percentage(text):
    if not text:
        return None

    text = normalize_digits(text)

    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)

    if not match:
        return None

    try:
        return float(match.group(1))
    except ValueError:
        return None


def extract_shipping(text):
    if not text:
        return 0.0

    text = normalize_digits(clean_text(text))

    free_words = [
        "توصيل مجاني", "شحن مجاني", "الشحن مجاني",
        "Free delivery", "Free Shipping", "free shipping", "FREE delivery",
    ]

    lowered = text.lower()

    for word in free_words:
        if word.lower() in lowered:
            return 0.0

    patterns = [
        r"([\d,.]+)\s*ريال",
        r"ريال\s*([\d,.]+)",
        r"([\d,.]+)\s*SAR",
        r"SAR\s*([\d,.]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                pass

    return 0.0
