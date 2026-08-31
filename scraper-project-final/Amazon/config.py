# ============================================================
# Amazon/config.py
# كل الإعدادات الثابتة الخاصة بسكرابر أمازون في مكان واحد
# ============================================================

from pathlib import Path

AMAZON_DOMAIN = "https://www.amazon.sa"

# --------------------------------------------------------------
# بس حط الـ ASINs هنا كـ list بسيط، من غير أي تعقيد
# --------------------------------------------------------------
ASINS = [
    "B0FX57821D",
    "B0C4FSDY9M",
    "B0GWFCT9N9",
    "B0CZ7N3RH8",
    "B0BXYRYCKW",
    "B0CFG5Q8BB",
    "B085PQRC6N",
    "B0F2N1CFPS",
    "B0GWFKWBT2",
    "B0F1N79TYM",
    "B0CZ6G8WN7",
    "B0F1GY8F7F",
    "B0F89DMTJD",
    "B0F89GKN53",
    "B08THLZ4K9",
    "B0F53P7P2K",
    "B0DYFBXXCZ",
    "B0DD56T63G",
    "B09BMZ9KVY",
    "B08QRXBYF4",
    "B0FHWBRPYV",
    "B00LM3958M",
    "B085VT1VJT",
    "B0HCCPTJFB",
    "B0HCCJHRC9",
    "B0HC3GSYZ2",
    "B0HC35NZB4",
    "B0C1W3MK86",
    "B01J5DYWTW",
    "B0HCCXNS63",
    "B0HCCVD637",
    "B0HCCR98GJ",
    "B0HCCLSNB8",
    "B0HCCGPNJY",
    "B0HCCGFDTV",
]

# اختياري: لو عندك اسم بائع واحد بيتكرر في كل المنتجات، حطه هنا
MY_SELLER_NAME = None  # مثال: "My Store Name"

# اختياري: سعرك انت لكل منتج (لو عايز نحسب هل انت أرخص من المنافسين ولا لأ)
MY_PRICES = {
    # "B0CZ7L2QN1": 199.00,
    # "B0CZ7N3RH8": 89.00,
}

# --------------------------------------------------------------
# ملفات الإخراج - داخل فولدر Amazon نفسه عشان يفضل كل حاجة بتاعت
# أمازون منظمة مع بعض ومنفصلة عن نون
#
# ⚠️ مهم: المسارات دي لازم تكون absolute (مبنية على مكان ملف
# config.py نفسه) مش relative، عشان تشتغل صح بغض النظر عن الـ
# working directory اللي بايثون شغال منه (ده اللي كان بيسبب مشكلة
# "الملف موجود بس مش بيتقرا" على Streamlit Cloud).
# --------------------------------------------------------------
_AMAZON_DIR = Path(__file__).resolve().parent

OUTPUT_JSON_FILE = str(_AMAZON_DIR / "all_offers.json")
OUTPUT_EXCEL_FILE = str(_AMAZON_DIR / "all_offers.xlsx")

# ملف "آخر تحديث فقط" - بيتكتب فيه أحدث سحب لكل منتج بس، وبيتمسح منه أي
# صف قديم لنفس الـ ASIN تلقائيًا. ده اللي Streamlit المفروض يقرا منه
# عشان الداشبورد يعرض آخر بيانات بس من غير خلط قديم/جديد.
OUTPUT_LAST_DATA_FILE = str(_AMAZON_DIR / "last_data.xlsx")

HEADLESS = True   # True للتشغيل التلقائي/الدوري. خليه False بس وانت بتصحح مشكلة.

# فلاجات ضرورية لتشغيل Chromium جوه container (زي Streamlit Cloud) اللي
# مفيهوش صلاحيات sandbox الطبيعية بتاعة المتصفح. من غيرهم Chromium
# بيكرش فورًا وقت اللانش (ده سبب شائع جدًا لـ "شغال لوكال، مش شغال
# على السيرفر"). محليًا مش هتأثر بحاجة، الفلاجات دي آمنة تتفعل دايمًا.
BROWSER_LAUNCH_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
]

MAX_LOAD_ROUNDS = 40   # قللناها من 100 لتسريع كل تشغيلة (كانت ممكن تاخد لحد 6-7 دقايق)
MAX_NO_CHANGE = 5

# IMPORTANT:
# Never deduplicate AOD offers by seller / price / shipping.
# Every DOM offer gets its own offer_id.
