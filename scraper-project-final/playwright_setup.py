# ============================================================
# playwright_setup.py
# على جهازك بتعمل "playwright install chromium" يدوي مرة واحدة.
# لكن على Streamlit Cloud مفيش وصول للـ terminal، فالدالة دي بتنزّل
# متصفح Chromium تلقائيًا أول مرة التطبيق يشتغل فيها.
# ============================================================

import subprocess
import sys

import streamlit as st


@st.cache_resource(show_spinner="بيتم تجهيز متصفح السكرابر (أول مرة بس، ممكن ياخد دقيقة)...")
def ensure_playwright_browser():
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True, capture_output=True, text=True, timeout=300,
        )
        print("[+] Playwright Chromium جاهز.")
    except Exception as e:
        print(f"[!] تعذر تجهيز Playwright Chromium تلقائيًا: {e}")
        print("[!] لو السكرابر فشل، جرب تضيف مكتبات النظام المطلوبة عن طريق packages.txt")
    return True
