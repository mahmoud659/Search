# ============================================================
# scheduler.py
# بيشغّل Amazon.amazon.run_all() تلقائيًا كل 12 ساعة، جوه نفس
# عملية Streamlit، باستخدام APScheduler.
#
# ⚠️ ملاحظة مهمة (اقرأها):
# ده بيشتغل بس طول ما عملية Streamlit شغالة وحية. لو التطبيق على
# Streamlit Community Cloud "نام" بسبب عدم وجود زوار (الخطة المجانية
# بتوقف التطبيقات الخاملة تلقائيًا)، الجدولة بتوقف معاه، وترجع تشتغل
# تاني (وتعمل سحب فوري) أول ما حد يفتح التطبيق تاني. يعني الجدولة دي
# "بأفضل مجهود" مش مضمونة 100% كل 12 ساعة بالظبط لو مفيش زوار خالص.
# لضمان تشغيل دوري مضمون بغض النظر عن الزوار، الحل الأنسب هو جدولة
# خارجية (GitHub Actions / Cron Server) تستدعي نفس كود السكرابر
# وتحدّث نفس الملفات بشكل مستقل عن التطبيق.
# ============================================================

from datetime import datetime

import streamlit as st


def _run_and_log():
    print(f"[SCHEDULER] بدء تشغيل دوري تلقائي: {datetime.now().isoformat()}")
    try:
        from Amazon.amazon import run_all as run_amazon_scrape  # lazy import - شايف السبب في streamlit_app.py
        run_amazon_scrape()
    except Exception as e:
        print(f"[SCHEDULER] فشلت التشغيلة الدورية: {e}")


@st.cache_resource(show_spinner=False)
def start_background_scheduler():
    """
    @st.cache_resource بتضمن إن الجدولة تتعمل مرة واحدة بس لكل عملية
    Streamlit (مش مرة لكل مستخدم أو كل rerun)، وإلا كنا هنلاقي أكتر
    من scheduler شغال في نفس الوقت.

    لو apscheduler أو playwright مش متثبتين صح، الدالة بترجع None
    والداشبورد يفضل شغال عادي من غير الجدولة التلقائية.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception as e:
        print(f"[SCHEDULER] apscheduler مش متاحة، الجدولة التلقائية معطّلة: {e}")
        return None

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        _run_and_log,
        trigger="interval",
        hours=12,
        id="amazon_scrape_every_12h",
        next_run_time=datetime.now(),  # أول تشغيلة فورية عند بدء التطبيق
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    print("[SCHEDULER] تم تفعيل الجدولة التلقائية (كل 12 ساعة).")
    return scheduler
