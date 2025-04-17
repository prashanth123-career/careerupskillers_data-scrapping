import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import re
import zipfile
import random
from io import BytesIO
from time import sleep
from urllib.parse import urlparse
from PIL import Image

# --- CONFIG ---
REQUEST_DELAY = 1.5
IMAGE_FOLDER = "scraped_images"
LOG_FILE = "scrape_log.txt"
os.makedirs(IMAGE_FOLDER, exist_ok=True)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    'Mozilla/5.0 (X11; Linux x86_64)',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)'
]

PROXIES = [
    None,
    # Add your proxy dicts here
]

# --- STREAMLIT CONFIG ---
st.set_page_config(page_title="Universal Web Scraper", layout="centered")
st.title("🌐 Universal Web Scraper")
st.markdown("Scrape any public website easily, even if you're not technical.")

# --- HELP TIPS ---
st.markdown("""
#### 👇 Need help picking a selector?
- To extract links → type: `a`
- To extract images → type: `img`
- To extract article titles → try: `h2 a`
- For anything else, right-click on the item in your browser → click **Inspect** → copy **CSS selector**.

#### 🔍 Attribute Options:
- `href` → for links
- `src` → for images
- `inner text` → to extract the actual visible text
""")

# --- INPUT FORM ---
with st.form("scraper_inputs"):
    target_url = st.text_input("🔗 Website URL", "https://example.com")
    selector_tag = st.text_input("📌 What to extract (CSS selector)", "a")
    attribute = st.selectbox("📤 What data to extract?", ["href", "src", "inner text"])
    max_items = st.slider("📊 How many items to extract?", 1, 200, 20)
    max_retries = st.slider("🔁 Retry on failure (times)", 0, 5, 2)
    submit = st.form_submit_button("🚀 Start Scraping")

if submit:
    all_data = []

    def log_error(msg):
        with open(LOG_FILE, "a") as f:
            f.write(msg + "\n")

    def get_random_headers():
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "en-US,en;q=0.9"
        }

    def fetch_url(url):
        for attempt in range(max_retries + 1):
            try:
                r = requests.get(url, headers=get_random_headers(), timeout=10, proxies=random.choice(PROXIES))
                r.raise_for_status()
                return r.text
            except Exception as e:
                log_error(f"Attempt {attempt+1} failed for {url}: {e}")
                sleep(REQUEST_DELAY)
        return None

    def download_image(url, label):
        try:
            r = requests.get(url, headers=get_random_headers(), stream=True, timeout=15)
            r.raise_for_status()
            filename = os.path.join(IMAGE_FOLDER, re.sub(r'[^\w\-_\. ]', '_', label)[:40] + os.path.splitext(urlparse(url).path)[1])
            with open(filename, "wb") as f:
                f.write(r.content)
            return filename
        except Exception as e:
            log_error(f"Image download failed for {url}: {e}")
            return ""

    st.info(f"Scraping data from: {target_url}")
    html = fetch_url(target_url)

    if html:
        soup = BeautifulSoup(html, "html.parser")
        elements = soup.select(selector_tag)

        for i, elem in enumerate(elements[:max_items]):
            entry = {}
            if attribute == "inner text":
                entry["Content"] = elem.get_text(strip=True)
            else:
                entry[attribute] = elem.get(attribute, "N/A")

            if attribute in ["src", "href"] and str(entry.get(attribute)).lower().endswith(('.jpg', '.png', '.jpeg')):
                img_path = download_image(entry[attribute], f"image_{i}")
                entry["Image File"] = os.path.basename(img_path)

            all_data.append(entry)
            sleep(REQUEST_DELAY)

        df = pd.DataFrame(all_data)
        excel_file = "scraped_data.xlsx"
        df.to_excel(excel_file, index=False)

        st.success(f"✅ Scraped {len(df)} items!")
        st.dataframe(df)

        with open(excel_file, "rb") as f:
            st.download_button("📥 Download Excel", f, file_name=excel_file)

        image_files = [os.path.join(IMAGE_FOLDER, f) for f in os.listdir(IMAGE_FOLDER)]
        if image_files:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for img in image_files:
                    zipf.write(img, os.path.basename(img))
            zip_buffer.seek(0)
            st.download_button("📦 Download All Images (ZIP)", zip_buffer, file_name="images.zip", mime="application/zip")

st.markdown("""
<style>
    .stDownloadButton button {
        width: 100%;
        transition: all 0.2s;
    }
    .stDownloadButton button:hover {
        transform: scale(1.02);
    }
    .stSpinner > div {
        justify-content: center;
    }
</style>
""", unsafe_allow_html=True)
