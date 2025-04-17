import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import re
import zipfile
from io import BytesIO
from time import sleep
from urllib.parse import urlparse

# --- CONFIG ---
REQUEST_DELAY = 1.5
IMAGE_FOLDER = "seed_images"
os.makedirs(IMAGE_FOLDER, exist_ok=True)

st.set_page_config(page_title="🌱 OSC Seeds Scraper", layout="centered")
st.title("🌱 OSC Seeds Product Scraper")
st.markdown("Select a category from OSCSeeds.com, see how many products it has, and extract details instantly!")

# --- STEP 1: FETCH CATEGORIES ---
@st.cache_data
def get_categories():
    url = "https://www.oscseeds.com/shop/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")
    categories = {}
    for a in soup.select("ul.product-categories li a"):
        name = a.get_text(strip=True)
        href = a.get("href")
        if name and href:
            categories[name] = href
    return categories

categories = get_categories()
category_name = st.selectbox("Select a Product Category", list(categories.keys()))
selected_url = categories[category_name]

# --- STEP 2: GET PRODUCT COUNT ---
@st.cache_data
def get_total_product_count(category_url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(category_url, headers=headers)
    soup = BeautifulSoup(r.text, "html.parser")
    product_items = soup.select("li.product a.woocommerce-LoopProduct-link")
    if not product_items:
        return 0
    # Get count by pagination (optional: use real count if available)
    page = 1
    total_links = []
    while True:
        url = f"{category_url}page/{page}/" if page > 1 else category_url
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, "html.parser")
        links = [a.get("href") for a in soup.select("li.product a.woocommerce-LoopProduct-link")]
        if not links:
            break
        total_links += links
        page += 1
        sleep(0.5)
    return len(set(total_links))

total_products = get_total_product_count(selected_url)
st.success(f"✅ {total_products} products found in '{category_name}'")

max_products = st.slider("How many products do you want to scrape?", 1, total_products, min(10, total_products))

# --- STEP 3: SCRAPING FUNCTIONS ---
def get_product_links(base_url, limit):
    headers = {'User-Agent': 'Mozilla/5.0'}
    links = []
    page = 1
    while len(links) < limit:
        url = f"{base_url}page/{page}/" if page > 1 else base_url
        try:
            r = requests.get(url, headers=headers)
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.select("li.product a.woocommerce-LoopProduct-link"):
                href = a.get("href")
                if href and href not in links:
                    links.append(href)
                    if len(links) >= limit:
                        break
            page += 1
            sleep(0.5)
        except:
            break
    return links

def download_image(img_url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(img_url, headers=headers, stream=True)
        if r.status_code == 200:
            filename = os.path.basename(urlparse(img_url).path)
            filepath = os.path.join(IMAGE_FOLDER, filename)
            with open(filepath, 'wb') as f:
                f.write(r.content)
            return filepath
    except:
        return ""
    return ""

def scrape_product(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers)
        soup = BeautifulSoup(r.text, 'html.parser')
        title = soup.select_one("h1.product_title")
        price = soup.select_one("p.price")
        desc = soup.select_one("div.woocommerce-product-details__short-description")
        img = soup.select_one("div.woocommerce-product-gallery__image img")

        data = {
            "Product Name": title.get_text(strip=True) if title else "N/A",
            "Price": price.get_text(strip=True) if price else "N/A",
            "Description": desc.get_text(strip=True) if desc else "N/A",
            "Product URL": url,
            "Image File": ""
        }

        if img and img.get("src"):
            img_path = download_image(img.get("src"))
            if img_path:
                data["Image File"] = os.path.basename(img_path)
                image_files.append(img_path)

        return data
    except Exception as e:
        st.warning(f"Failed: {url} - {e}")
        return None

# --- STEP 4: RUN SCRAPER ---
if st.button("Start Scraping"):
    image_files = []
    all_products = []

    st.info(f"Scraping {max_products} products from {category_name}...")
    product_links = get_product_links(selected_url, max_products)

    progress = st.progress(0)
    status = st.empty()

    for i, link in enumerate(product_links, 1):
        status.text(f"Scraping {i}/{len(product_links)}...")
        data = scrape_product(link)
        if data:
            all_products.append(data)
        progress.progress(i / len(product_links))
        sleep(REQUEST_DELAY)

    progress.empty()
    status.empty()

    if not all_products:
        st.error("No data extracted.")
        st.stop()

    df = pd.DataFrame(all_products)
    excel_file = "osc_products.xlsx"
    df.to_excel(excel_file, index=False)

    # --- DOWNLOADS ---
    st.success(f"✅ Scraped {len(df)} products from {category_name}")

    col1, col2 = st.columns(2)
    with col1:
        with open(excel_file, "rb") as f:
            st.download_button("📥 Download Excel", f, file_name=excel_file)

    with col2:
        if image_files:
            zip_buffer = BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for img_path in image_files:
                    zipf.write(img_path, os.path.basename(img_path))
            zip_buffer.seek(0)
            st.download_button("📦 Download Images (ZIP)", data=zip_buffer, file_name="osc_seeds_images.zip", mime="application/zip")
        else:
            st.warning("No images found.")

# --- STYLE ---
st.markdown("""
<style>
    .stDownloadButton button { width: 100%; }
    .stSpinner > div { justify-content: center; }
</style>
""", unsafe_allow_html=True)
