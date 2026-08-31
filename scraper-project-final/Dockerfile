# ============================================================
# Dockerfile
#
# ده الحل النهائي لمشكلة "Chromium مش شغال على السيرفر" - بيبني
# image فيه Python + كل مكتبات النظام + متصفح Chromium متثبتين
# بشكل مضمون 100% (لأن الـ build بيحصل بصلاحيات root كاملة، عكس
# packages.txt على Streamlit Community Cloud اللي مش واضح ليه مش
# بيشتغل في بيئتك الحالية).
#
# يشتغل على أي منصة بتدعم Docker: Render, Railway, Fly.io,
# Google Cloud Run, Azure Container Apps, إلخ.
# ============================================================

FROM python:3.12-slim

WORKDIR /app

# مكتبات النظام اللي Chromium محتاجها (نفس القايمة اللي حاولنا
# نحطها في packages.txt، بس هنا مضمون إنها هتتثبت لأن الـ build
# بيحصل بصلاحيات root)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    libxrender1 \
    libxshmfence1 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# بيثبت متصفح Chromium نفسه (الـ binary) - ده اللي كان بيفشل
# يتحمل صح على Streamlit Cloud. هنا مضمون لأن الصلاحيات كاملة.
RUN playwright install chromium

COPY . .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
