# ============================================================
# Amazon/browser.py
# أي حاجة بتتعامل مباشرة مع Playwright (page.locator, click,
# scroll...) بتتحط هنا. الهدف إن الملف ده هو الوحيد اللي بيعرف
# إزاي "يمشي" جوه الصفحة، من غير ما يهتم بتفاصيل الـ parsing.
# ============================================================

import re

from .config import MAX_LOAD_ROUNDS, MAX_NO_CHANGE
from .utils import clean_text, normalize_digits


# ============================================================
# AOD DOM (Amazon Other Sellers)
# ============================================================

def get_aod_offer_count(page):
    try:
        return page.locator("#aod-offer").count()
    except Exception:
        return 0


def get_aod_html_snapshots(page):
    try:
        return page.locator("#aod-offer").evaluate_all(
            "elements => elements.map(element => element.outerHTML)"
        )
    except Exception as e:
        print(f"[!] Could not capture AOD HTML: {e}")
        return []


def scroll_aod_container(page):
    try:
        offers = page.locator("#aod-offer")
        count = offers.count()
        if count > 0:
            offers.nth(count - 1).scroll_into_view_if_needed(timeout=5000)
            page.wait_for_timeout(1500)
        page.mouse.wheel(0, 900)
        page.wait_for_timeout(1200)
        return True
    except Exception as e:
        print(f"[!] AOD scroll warning: {e}")
        return False


def find_aod_show_more(page):
    selectors = [
        "#aod-pinned-offer-show-more", "#aod-load-more", "#aod-load-more-button",
        "#aod-show-more", "input[value*='عرض المزيد']", "input[value*='Show more']",
        "button:has-text('عرض المزيد')", "button:has-text('Show more')",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector)
            count = locator.count()
            for i in range(count):
                button = locator.nth(i)
                try:
                    if not button.is_visible():
                        continue
                    text = clean_text(button.inner_text(timeout=1000)) or clean_text(button.get_attribute("value"))
                    if not text:
                        continue
                    allowed = ["عرض المزيد", "Show more", "more"]
                    if any(word.lower() in text.lower() for word in allowed):
                        return button
                except Exception:
                    continue
        except Exception:
            continue
    return None


def load_all_aod_offers(page):
    print()
    print("=" * 70)
    print("LOADING ALL AMAZON OTHER SELLERS")
    print("=" * 70)

    captured_snapshots = []
    seen_snapshot_keys = set()
    no_change = 0

    for round_number in range(1, MAX_LOAD_ROUNDS + 1):
        current_count = get_aod_offer_count(page)
        print(f"\n[+] Load round {round_number}")
        print(f"[+] AOD offers currently loaded: {current_count}")

        before_total = len(captured_snapshots)

        current_html = get_aod_html_snapshots(page)
        for html in current_html:
            if not html:
                continue
            key = hash(html)
            if key not in seen_snapshot_keys:
                seen_snapshot_keys.add(key)
                captured_snapshots.append(html)

        scroll_aod_container(page)
        after_scroll = get_aod_offer_count(page)
        print(f"[+] Offers after scroll: {after_scroll}")

        current_html = get_aod_html_snapshots(page)
        for html in current_html:
            if not html:
                continue
            key = hash(html)
            if key not in seen_snapshot_keys:
                seen_snapshot_keys.add(key)
                captured_snapshots.append(html)

        print(f"[+] Visible AOD offers: {after_scroll}")
        print(f"[+] Total captured AOD snapshots: {len(captured_snapshots)}")

        button = find_aod_show_more(page)
        if button:
            try:
                text = clean_text(button.inner_text(timeout=1000)) or "Show more"
                print(f"[+] Clicking AOD load-more: {text}")
                button.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                button.click(timeout=5000)
                page.wait_for_timeout(2500)

                current_html = get_aod_html_snapshots(page)
                for html in current_html:
                    if not html:
                        continue
                    key = hash(html)
                    if key not in seen_snapshot_keys:
                        seen_snapshot_keys.add(key)
                        captured_snapshots.append(html)

                print(f"[+] Offers after load-more: {get_aod_offer_count(page)}")
            except Exception as e:
                print(f"[!] Show More click failed: {e}")
        else:
            print("[+] No AOD Show More button found.")

        added = len(captured_snapshots) - before_total
        if added > 0:
            print(f"[+] New AOD DOM snapshots: {added}")
            no_change = 0
        else:
            no_change += 1
            print(f"[+] No new AOD offers ({no_change}/{MAX_NO_CHANGE})")

        if no_change >= MAX_NO_CHANGE:
            print("\n[+] No more AOD offers detected.")
            break

    final_visible = get_aod_offer_count(page)
    print("\n" + "=" * 70)
    print(f"[+] FINAL VISIBLE AOD COUNT: {final_visible}")
    print(f"[+] TOTAL CAPTURED AOD SNAPSHOTS: {len(captured_snapshots)}")
    print("=" * 70)

    return captured_snapshots


# ============================================================
# CURRENT OFFER - جمع الـ HTML بتاع المرشحين (البارسنج نفسه في parser.py)
# ============================================================

def get_current_offer_html_candidates(page):
    """
    بيدور على كل الحاويات اللي ممكن يكون فيها العرض الحالي (buybox)
    وبيرجع outerHTML بتاعهم عشان يتبعتوا لـ parser.py يستخرج منهم
    السعر/البائع/الخصم.
    """
    selectors = [
        "#desktop_buybox", "#buybox_feature_div", "#buyBoxAccordion",
        "#buybox", "#rightCol", "#centerCol", "#corePriceDisplay_desktop_feature_div",
    ]

    candidates_html = []
    for selector in selectors:
        try:
            locator = page.locator(selector)
            for i in range(locator.count()):
                try:
                    if not locator.nth(i).is_visible():
                        continue
                    html = locator.nth(i).evaluate("element => element.outerHTML")
                    if html:
                        candidates_html.append(html)
                except Exception:
                    continue
        except Exception:
            continue

    return candidates_html


def wait_for_aod_section(page, timeout=20000):
    """بيرجع True لو لقى قسم 'بائعين تانيين' جوه الصفحة."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError  # lazy import عمدًا
    try:
        page.locator("#aod-offer").first.wait_for(state="attached", timeout=timeout)
        return True
    except PlaywrightTimeoutError:
        return False


# ============================================================
# تقييم المنتج نفسه (النجوم العامة اللي كل الزباين شايفينها،
# بغض النظر عن مين البائع)
# ============================================================

def extract_product_rating(page):
    rating = None
    review_count = None

    # جرب أول حاجة الطريقة الأدق (كلاس CSS يشفّر النجوم مباشرة)
    try:
        star_loc = page.locator("#acrPopover [class*='a-star']").first
        if star_loc.count() > 0:
            class_attr = star_loc.get_attribute("class") or ""
            m = re.search(r"a-star(?:-mini)?-(\d)(?:-(\d))?\b", class_attr)
            if m:
                whole = int(m.group(1))
                frac = m.group(2)
                candidate = whole + (int(frac) / 10 if frac else 0)
                if 0 <= candidate <= 5:
                    rating = candidate
    except Exception:
        pass

    # لو الكلاس ما نفعش، نرجع للطريقة النصية القديمة
    if rating is None:
        rating_selectors = [
            "#acrPopover span.a-icon-alt",
            "span.a-icon-alt",
            "#averageCustomerReviews span.a-icon-alt",
        ]
        for selector in rating_selectors:
            try:
                loc = page.locator(selector).first
                if loc.count() > 0:
                    text = clean_text(loc.inner_text(timeout=2000))
                    if text:
                        text = normalize_digits(text)
                        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:من|out of)\s*5", text, re.IGNORECASE)
                        if m:
                            rating = float(m.group(1))
                            break
            except Exception:
                continue

    review_selectors = [
        "#acrCustomerReviewText",
        "#averageCustomerReviews_feature_div #acrCustomerReviewText",
    ]
    for selector in review_selectors:
        try:
            loc = page.locator(selector).first
            if loc.count() > 0:
                text = clean_text(loc.inner_text(timeout=2000))
                if text:
                    text = normalize_digits(text)
                    m = re.search(r"([\d,]+)", text)
                    if m:
                        review_count = int(m.group(1).replace(",", ""))
                        break
        except Exception:
            continue

    return rating, review_count


# ============================================================
# NEW: بيانات المنتج الأساسي بس - العنوان + الوصف + الصورة
# ============================================================

def extract_product_info(page):
    """
    بيرجع (title, description, image_url) للمنتج الأساسي بس
    (مش لكل عرض/بائع - مرة واحدة للصفحة كلها).
    """
    title = None
    description = None
    image_url = None

    # -------- العنوان --------
    title_selectors = ["#productTitle", "#title span#productTitle", "h1#title"]
    for selector in title_selectors:
        try:
            loc = page.locator(selector).first
            if loc.count() > 0:
                text = clean_text(loc.inner_text(timeout=2000))
                if text:
                    title = text
                    break
        except Exception:
            continue

    # -------- الوصف --------
    description_selectors = [
        "#productDescription",
        "#feature-bullets",
        "#aplus",
    ]
    for selector in description_selectors:
        try:
            loc = page.locator(selector).first
            if loc.count() > 0:
                text = clean_text(loc.inner_text(timeout=2000))
                if text:
                    # نحدد طول الوصف عشان ميبقاش ضخم جدًا جوه الإكسيل
                    description = text[:2000]
                    break
        except Exception:
            continue

    # -------- الصورة الرئيسية --------
    image_selectors = ["#landingImage", "#imgTagWrapperId img", "#main-image"]
    for selector in image_selectors:
        try:
            loc = page.locator(selector).first
            if loc.count() > 0:
                src = (
                    loc.get_attribute("data-old-hires")
                    or loc.get_attribute("src")
                    or loc.get_attribute("data-a-hires")
                )
                if src:
                    image_url = src
                    break
        except Exception:
            continue

    return title, description, image_url
