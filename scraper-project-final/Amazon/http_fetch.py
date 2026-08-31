# ============================================================
# Amazon/http_fetch.py
#
# طريقة بديلة لجلب بيانات المنتج من غير أي متصفح (Playwright) خالص -
# بس طلب HTTP عادي بمكتبة requests. بتُستخدم كـ fallback تلقائي لو
# Playwright/Chromium مش شغال على السيرفر (زي المشكلة المتكررة على
# Streamlit Cloud مع مكتبات النظام الناقصة).
#
# القيود المعروفة (بصراحة):
# - أمازون بترندر أول دفعة بس من عروض البائعين (AOD) في الـ HTML
#   الأساسي؛ باقي العروض بتتحمل عن طريق JS بعد الضغط على "تحميل
#   المزيد"، وده مش هيحصل من غير متصفح حقيقي. يعني ممكن تجيب عدد
#   عروض أقل من الطريقة اللي بتستخدم Playwright.
# - أمازون أحيانًا بترجع صفحة تحقق (CAPTCHA) لو الطلبات كتّرت من نفس
#   الـ IP. الكود بيتعامل مع الفشل برفع Exception واضح بدل ما يتوهم
#   إنه لقى بيانات فاضية.
# - رغم القيود دي، لسه أفضل من صفر بيانات لما المتصفح كله مش شغال.
# ============================================================

import requests

from . import parser
from .config import AMAZON_DOMAIN

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ar-SA,ar;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Chromium";v="125", "Not.A/Brand";v="24", "Google Chrome";v="125"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
}

REQUEST_TIMEOUT = 20

# نستخدم Session واحدة (مش requests.get منفصلة كل مرة) عشان الكوكيز
# اللي أمازون بتحطها في أول طلب تتبعت تلقائي في الطلب اللي بعده - ده
# بيقلل احتمال الحظر (403) شوية، لأنه بيشبه سلوك متصفح حقيقي أكتر من
# طلبات منفصلة بدون حالة.
_session = requests.Session()
_session.headers.update(REQUEST_HEADERS)


def _fetch_html(url, referer=None):
    headers = {"Referer": referer} if referer else {}
    response = _session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def _warm_up():
    """
    زيارة سريعة للصفحة الرئيسية الأول عشان الـ Session تاخد كوكيز
    أساسية من أمازون قبل ما تطلب صفحة منتج مباشرة - ده بيقلل احتمال
    الحظر (403) لأنه أقرب لسلوك متصفح حقيقي (محدش بيفتح صفحة منتج
    من غير ما يزور الموقع الأساسي الأول أبدًا).
    """
    try:
        _session.get(AMAZON_DOMAIN, timeout=REQUEST_TIMEOUT)
    except Exception:
        pass  # مش مشكلة لو فشلت - هي تحسين اختياري بس


def fetch_offer_data(asin, referer=None):
    """
    بيرجع (current_offer, aod_offers, page_url) لمنتج معين، بدون متصفح،
    باستخدام نفس دوال parser.py المستخدمة مع Playwright بالظبط.
    """
    offer_url = f"{AMAZON_DOMAIN}/gp/offer-listing/{asin}?condition=NEW"
    html = _fetch_html(offer_url, referer=referer)

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # نمرر الصفحة كاملة كـ "مرشح واحد" لـ parse_current_offer، وهو أصلاً
    # بيدور جوه الصفحة عن أول سعر فعلي يلاقيه - بيشتغل صح حتى لو الصفحة
    # كاملة مش container واحد بس
    current_offer = parser.parse_current_offer([html], offer_url)

    # عروض البائعين التانيين - كل عنصر id="aod-offer" (أمازون بتكرر نفس
    # الـ id عمدًا لكل عرض؛ BeautifulSoup زي المتصفح بيلاقيهم كلهم)
    aod_snapshots = [str(el) for el in soup.select("#aod-offer")]
    aod_offers = parser.extract_aod_offers_from_snapshots(aod_snapshots)

    return current_offer, aod_offers, offer_url


def fetch_product_info(asin):
    """بيرجع (title, description, image_url) لصفحة المنتج نفسه، بدون متصفح."""
    from bs4 import BeautifulSoup

    product_url = f"{AMAZON_DOMAIN}/dp/{asin}"
    html = _fetch_html(product_url, referer=AMAZON_DOMAIN)
    soup = BeautifulSoup(html, "html.parser")

    title = None
    title_el = soup.select_one("#productTitle")
    if title_el:
        title = parser.clean_text(title_el.get_text(" ", strip=True))

    description = None
    for selector in ["#productDescription", "#feature-bullets", "#aplus"]:
        el = soup.select_one(selector)
        if el:
            text = parser.clean_text(el.get_text(" ", strip=True))
            if text:
                description = text[:2000]
                break

    image_url = None
    for selector in ["#landingImage", "#imgTagWrapperId img", "#main-image"]:
        el = soup.select_one(selector)
        if el:
            src = el.get("data-old-hires") or el.get("src") or el.get("data-a-hires")
            if src:
                image_url = src
                break

    return title, description, image_url
