# ============================================================
# auth.py
# صفحة تسجيل الدخول. البيانات (الإيميلات والباسوردات) مش مكتوبة
# جوه الكود خالص - بتتقرأ من st.secrets (ملف .streamlit/secrets.toml
# محليًا، أو من "Secrets" في إعدادات التطبيق على Streamlit Cloud).
# ============================================================

import streamlit as st

ADMIN_KEYS = ["admin_1", "admin_2", "admin_3"]


def _get_credentials():
    """بيرجع dict فيه بيانات كل أدمن من st.secrets. لو الملف مش
    موجود أو ناقص، بيرجع dict فاضي بدل ما يكرش."""
    creds = {}
    for key in ADMIN_KEYS:
        entry = st.secrets.get(key)
        if entry:
            creds[key] = {
                "email": str(entry.get("email", "")).strip().lower(),
                "password": str(entry.get("password", "")),
            }
    return creds


def check_login():
    """
    بيرجع True لو المستخدم مسجل دخول، وبيرسم فورم تسجيل الدخول لو لسه لأ.
    """
    if st.session_state.get("authenticated"):
        return True

    st.title("🔐 تسجيل الدخول")
    st.caption("محتاج تسجل دخول عشان تشوف لوحة أسعار المنتجات")

    credentials = _get_credentials()
    if not credentials:
        st.error(
            "مفيش بيانات دخول متسجلة. أضف بيانات admin_1 / admin_2 / admin_3 "
            "في ملف `.streamlit/secrets.toml` محليًا، أو في Secrets من إعدادات "
            "التطبيق على Streamlit Cloud."
        )
        return False

    with st.form("login_form"):
        email = st.text_input("البريد الإلكتروني")
        password = st.text_input("كلمة المرور", type="password")
        submitted = st.form_submit_button("دخول")

    if submitted:
        email_clean = email.strip().lower()
        for admin_key, creds in credentials.items():
            if email_clean == creds["email"] and password == creds["password"]:
                st.session_state.authenticated = True
                st.session_state.current_admin = admin_key
                st.rerun()

        st.error("البريد الإلكتروني أو كلمة المرور غير صحيحة")

    return False


def logout_button():
    display_name = st.session_state.get("current_admin", "").replace("_", " ").title()
    st.sidebar.markdown(f"👤 مسجل دخول كـ: **{display_name}**")
    if st.sidebar.button("🚪 تسجيل الخروج"):
        st.session_state.authenticated = False
        st.session_state.pop("current_admin", None)
        st.rerun()
