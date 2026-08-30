# ============================================================
# streamlit_app.py
# صفحة عرض المنتجات + المنافسين، بتقرأ مباشرة من ملف
# Amazon/last_data.xlsx (آخر تحديث فقط لكل منتج، بشيتين:
# "Offers" و"Products")
#
# تشغيل محلي:
#   pip install streamlit pandas openpyxl playwright
#   playwright install chromium
#   streamlit run streamlit_app.py
# ============================================================

import os

import pandas as pd
import streamlit as st

from Amazon.amazon import scrape_sellers
from Amazon.config import MY_PRICES, MY_SELLER_NAME
from auth import check_login, logout_button
from playwright_setup import ensure_playwright_browser
from scheduler import start_background_scheduler

# --------------------------------------------------------------
# إعدادات الصفحة
# --------------------------------------------------------------
st.set_page_config(
    page_title="مقارنة أسعار المنتجات",
    page_icon="🛒",
    layout="wide",
)

# -------- تسجيل الدخول: لازم يعدي قبل أي حاجة تانية في الصفحة --------
if not check_login():
    st.stop()

# -------- تجهيز متصفح Playwright (لازم قبل أي سكرابينج) --------
ensure_playwright_browser()

# -------- الجدولة التلقائية كل 12 ساعة (مرة واحدة بس لكل عملية) --------
start_background_scheduler()


# آخر تحديث فقط لكل منتج (مش الأرشيف التاريخي all_offers.xlsx)
DEFAULT_EXCEL_PATH = "Amazon/last_data.xlsx"
PLACEHOLDER_IMAGE = "https://placehold.co/400x400?text=No+Image"

# لون واحد بس بيتكرر في كل الصفحة (السعر، التمييز في الجدول، الكروت)
# عشان الألوان متبقاش متعددة ومربكة
ACCENT_BG = "#cfe8f3"
ACCENT_TEXT = "#0a0a0a"

# --------------------------------------------------------------
# تنسيق عام: اتجاه الصفحة RTL + شكل الكروت (لون واحد موحّد)
# --------------------------------------------------------------
st.markdown(
    f"""
    <style>
    html, body, [class*="css"] {{ direction: rtl; text-align: right; }}
    .product-card {{
        border: 1px solid #e6e6e6;
        border-radius: 12px;
        padding: 14px;
        background: #ffffff;
        height: 100%;
    }}
    .product-card img {{
        border-radius: 8px;
        object-fit: contain;
        width: 100%;
        height: 180px;
        background: #fafafa;
    }}
    .price-tag {{
        font-size: 22px;
        font-weight: 700;
        color: {ACCENT_TEXT};
        background: {ACCENT_BG};
        padding: 2px 10px;
        border-radius: 8px;
        display: inline-block;
    }}
    .muted {{ color: #7a7a7a; font-size: 13px; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------
# تحميل البيانات
# مفتاح الكاش بيتضمن "وقت آخر تعديل للملف" (mtime)، فأي مرة الملف
# يتغيّر على الديسك (بعد تشغيلة سكرابر جديدة) الكاش بيتجدد تلقائي
# من غير ما نحتاج زرار "تحديث" يدوي
# --------------------------------------------------------------
def _file_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


@st.cache_data(show_spinner="بيتم تحميل بيانات المنتجات...")
def load_data(file, _mtime):
    offers = pd.read_excel(file, sheet_name="Offers")
    products = pd.read_excel(file, sheet_name="Products")

    numeric_cols = [
        "Product Price", "Original Price", "Discount Amount",
        "Shipping", "Total", "Seller Rating",
    ]
    for col in numeric_cols:
        offers[col] = pd.to_numeric(offers[col], errors="coerce")

    offers["Date"] = pd.to_datetime(offers["Date"], errors="coerce")

    return offers, products


def build_summary(offers):
    """ملخص لكل ASIN: أقل سعر، عدد العروض، آخر تحديث"""
    summary = (
        offers.groupby("ASIN")
        .agg(
            min_total=("Total", "min"),
            max_total=("Total", "max"),
            offers_count=("Offer ID", "count"),
            last_update=("Date", "max"),
        )
        .reset_index()
    )
    return summary


def format_price(value):
    if pd.isna(value):
        return "—"
    return f"{value:,.2f} SAR"


def has_value(value):
    """بترجع False لو القيمة فاضية أو NaN أو '-' (اللي الإكسيل بيكتبها
    بدل الفراغ لما مفيش بيانات)، عشان منحاولش نعرض '-' كصورة أو رابط."""
    if pd.isna(value):
        return False
    text = str(value).strip()
    return bool(text) and text != "-"


def format_relative_time(ts):
    if pd.isna(ts):
        return "—"
    delta = pd.Timestamp.now() - ts
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "الآن"
    if minutes < 60:
        return f"من {minutes} دقيقة"
    hours = minutes // 60
    if hours < 24:
        return f"من {hours} ساعة"
    days = hours // 24
    return f"من {days} يوم"


# --------------------------------------------------------------
# الشريط الجانبي: اختيار الملف + بحث + فلترة
# --------------------------------------------------------------
st.sidebar.title("🛒 لوحة التحكم")
logout_button()
st.sidebar.markdown("---")

uploaded_file = st.sidebar.file_uploader(
    "ارفع ملف Excel (اختياري)", type=["xlsx"],
    help="لو مرفعتش ملف، هيتم تحميل الملف الافتراضي: " + DEFAULT_EXCEL_PATH,
)

if uploaded_file is not None:
    data_source, mtime_key = uploaded_file, None
else:
    data_source, mtime_key = DEFAULT_EXCEL_PATH, _file_mtime(DEFAULT_EXCEL_PATH)

try:
    offers_df, products_df = load_data(data_source, mtime_key)
except FileNotFoundError:
    st.error(
        f"مالقيتش الملف الافتراضي `{DEFAULT_EXCEL_PATH}`. "
        "ارفع ملف Excel من الشريط الجانبي، أو شغّل السكرابر الأول مرة عشان الملف يتعمل."
    )
    st.stop()
except Exception as e:
    st.error(f"حصلت مشكلة وانا بحاول أقرأ الملف: {e}")
    st.stop()

summary_df = build_summary(offers_df)
merged = products_df.merge(summary_df, on="ASIN", how="left")

search_term = st.sidebar.text_input("🔍 ابحث عن منتج", "")
sort_option = st.sidebar.selectbox(
    "ترتيب حسب",
    ["الأحدث تحديثًا", "الأقل سعرًا", "الأعلى سعرًا", "عدد العروض (الأكثر منافسة)"],
)

if search_term.strip():
    merged = merged[
        merged["Product Title"].str.contains(search_term, case=False, na=False)
        | merged["ASIN"].str.contains(search_term, case=False, na=False)
    ]

if sort_option == "الأحدث تحديثًا":
    merged = merged.sort_values("last_update", ascending=False)
elif sort_option == "الأقل سعرًا":
    merged = merged.sort_values("min_total", ascending=True)
elif sort_option == "الأعلى سعرًا":
    merged = merged.sort_values("min_total", ascending=False)
else:
    merged = merged.sort_values("offers_count", ascending=False)

st.sidebar.markdown("---")
st.sidebar.metric("عدد المنتجات المتابَعة", len(products_df))
st.sidebar.metric("إجمالي العروض المرصودة", len(offers_df))


# --------------------------------------------------------------
# التنقل بين "شبكة المنتجات" و"تفاصيل منتج واحد"
# --------------------------------------------------------------
if "selected_asin" not in st.session_state:
    st.session_state.selected_asin = None


def rescan_now(asin):
    """بيشغّل سحب حقيقي فوري (Playwright) لمنتج واحد بس دلوقتي،
    ويحدّث last_data.xlsx بأحدث نتيجة. بياخد وقت (10-30 ثانية) لأنه
    بيفتح متصفح فعلي على أمازون."""
    with st.spinner(f"بيتم البحث عن أحدث الأسعار لـ {asin} الآن..."):
        try:
            scrape_sellers(
                asin=asin,
                my_price=MY_PRICES.get(asin),
                my_seller_name=MY_SELLER_NAME,
            )
            st.cache_data.clear()
            st.success("تم تحديث السعر بنجاح!")
        except Exception as e:
            st.error(f"تعذر تحديث السعر دلوقتي: {e}")
    st.rerun()


def show_product_detail(asin):
    product_row = products_df[products_df["ASIN"] == asin].iloc[0]
    product_offers = offers_df[offers_df["ASIN"] == asin].sort_values("Total", ascending=True)

    col_back, col_rescan = st.columns([1, 1])
    with col_back:
        if st.button("← رجوع لكل المنتجات"):
            st.session_state.selected_asin = None
            st.rerun()
    with col_rescan:
        if st.button("🔍 ابحث عن أحدث الأسعار الآن", type="primary"):
            rescan_now(asin)

    st.markdown("---")

    col_img, col_info = st.columns([1, 2], gap="large")

    with col_img:
        image_url = product_row.get("Image URL")
        st.image(image_url if has_value(image_url) else PLACEHOLDER_IMAGE, width="stretch")
        product_url = product_row.get("Product URL")
        if has_value(product_url):
            st.markdown(f"[🔗 فتح المنتج على أمازون]({product_url})")

    with col_info:
        st.subheader(product_row.get("Product Title") or "بدون عنوان")
        st.caption(f"ASIN: {asin}")

        if not product_offers.empty:
            best = product_offers.iloc[0]
            m1, m2, m3 = st.columns(3)
            m1.metric("أفضل سعر إجمالي", format_price(best["Total"]))
            m2.metric("عدد العروض", len(product_offers))
            m3.metric("آخر تحديث", format_relative_time(best["Date"]))
            seller_name = best.get("Seller")
            st.markdown(f"أرخص عرض حاليًا من: **{seller_name if has_value(seller_name) else '—'}**")

        with st.expander("📄 عرض الوصف الكامل", expanded=False):
            description = product_row.get("Description")
            st.write(description if has_value(description) else "لا يوجد وصف متاح لهذا المنتج.")

    st.markdown("---")
    st.subheader("💰 مقارنة المنافسين")

    if product_offers.empty:
        st.info("لا توجد عروض مسجلة لهذا المنتج حتى الآن.")
        return

    cheapest_total = product_offers["Total"].min()

    display_cols = [
        "Seller", "Offer ID", "Product Price", "Original Price",
        "Discount Amount", "Shipping", "Total", "Seller Rating", "Date",
    ]
    styled = product_offers[display_cols].copy()
    styled["Date"] = styled["Date"].dt.strftime("%Y-%m-%d %H:%M")

    def highlight_cheapest(row):
        if row["Total"] == cheapest_total:
            return [f"background-color: {ACCENT_BG}; color: {ACCENT_TEXT}"] * len(row)
        return [""] * len(row)

    st.dataframe(
        styled.style.apply(highlight_cheapest, axis=1).format(
            {
                "Product Price": format_price,
                "Original Price": format_price,
                "Discount Amount": format_price,
                "Shipping": format_price,
                "Total": format_price,
                "Seller Rating": lambda v: "—" if pd.isna(v) else f"⭐ {v:.1f}",
            },
            na_rep="—",
        ),
        width="stretch",
        hide_index=True,
    )


def show_product_grid(products_to_show):
    if products_to_show.empty:
        st.info("مفيش منتجات مطابقة للبحث/الفلتر الحالي.")
        return

    cols_per_row = 3
    rows = [products_to_show.iloc[i:i + cols_per_row] for i in range(0, len(products_to_show), cols_per_row)]

    for chunk in rows:
        cols = st.columns(cols_per_row)
        for col, (_, product) in zip(cols, chunk.iterrows()):
            with col:
                image_url = product.get("Image URL")
                title = product.get("Product Title")
                title = title if has_value(title) else "بدون عنوان"
                short_title = title if len(str(title)) <= 60 else str(title)[:57] + "..."

                st.markdown('<div class="product-card">', unsafe_allow_html=True)
                st.image(image_url if has_value(image_url) else PLACEHOLDER_IMAGE)
                st.markdown(f"**{short_title}**")
                st.caption(f"ASIN: {product['ASIN']}")

                min_total = product.get("min_total")
                offers_count = product.get("offers_count")
                offers_count = 0 if pd.isna(offers_count) else int(offers_count)

                st.markdown(
                    f'<span class="price-tag">{format_price(min_total)}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<span class="muted">🧑‍🤝‍🧑 {offers_count} عرض متاح · '
                    f'🕒 آخر تحديث: {format_relative_time(product.get("last_update"))}</span>',
                    unsafe_allow_html=True,
                )

                if st.button("عرض التفاصيل والمنافسين", key=f"btn_{product['ASIN']}"):
                    st.session_state.selected_asin = product["ASIN"]
                    st.rerun()

                st.markdown("</div>", unsafe_allow_html=True)


# --------------------------------------------------------------
# التشغيل الفعلي للصفحة
# --------------------------------------------------------------
st.title("🛒 مقارنة أسعار المنتجات")

if st.session_state.selected_asin:
    show_product_detail(st.session_state.selected_asin)
else:
    st.caption(f"بيانات محدّثة من ملف: `{DEFAULT_EXCEL_PATH if uploaded_file is None else uploaded_file.name}`")
    show_product_grid(merged)

