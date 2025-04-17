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
from PIL import Image

# --- CONFIG ---
REQUEST_DELAY = 1.5
IMAGE_FOLDER = "seed_images"
os.makedirs(IMAGE_FOLDER, exist_ok=True)

st.set_page_config(page_title="\ud83c\udf31 OSC Seeds Scraper", layout="centered")
st.title("\ud83c\udf31 OSC Seeds Product Scraper")
st.markdown("Select a category from OSCSeeds.com, see how many products it has, and extract details instantly!")

# --- FUNCTIONS ---
def get_total_products_and_links(category_url, max_pages=30):
    headers = {'User-Agent': 'Mozilla/5.0'}
    product_links = []
    seen = set()
    page = 1

    while page <= max_pages:
        url = f"{category_url}page/{page}/" if page > 1 else category_url
        try:
            r = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            links = [a.get("href").split('?')[0] for a in soup.select("li.product a.woocommerce-LoopProduct-link")]
            if not links:
                break
            for link in links:
                if link and link not in seen:
                    seen.add(link)
                    product_links.append(link)
            page += 1
            sleep(1)
        except Exception as e:
            st.warning(f"Failed to load page {page}: {e}")
            break

    return len(product_links), product_links

def download_image(img_url, product_name):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        if not img_url.startswith('http'):
            return ""

        response = requests.get(img_url, headers=headers, stream=True, timeout=15)
        response.raise_for_status()

        safe_name = re.sub(r'[^\w\-_\. ]', '_', product_name)[:50]
        ext = os.path.splitext(urlparse(img_url).path)[1][:4] or '.jpg'
        filename = f"{safe_name}{ext}"
        filepath = os.path.join(IMAGE_FOLDER, filename)

        with Image.open(BytesIO(response.content)) as img:
            img.save(filepath)

        return filepath
    except Exception as e:
        st.warning(f"Couldn't download image for {product_name}: {str(e)}")
        return ""

def scrape_product(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        name = (soup.select_one("h1.product_title") or soup.select_one("h1.entry-title"))
        price = (soup.select_one("p.price") or soup.select_one("span.woocommerce-Price-amount"))
        desc = (soup.select_one("div.woocommerce-product-details__short-description") or 
                soup.select_one("div.product_meta") or 
                soup.select_one("div.product_description"))
        img = (soup.select_one("div.woocommerce-product-gallery__image img") or 
               soup.select_one("img.wp-post-image") or 
               soup.select_one("img.attachment-woocommerce_single"))

        data = {
            "Product Name": name.get_text(strip=True) if name else "N/A",
            "Price": re.sub(r'\s+', ' ', price.get_text(strip=True)) if price else "N/A",
            "Description": desc.get_text(" ", strip=True) if desc else "N/A",
            "Product URL": url,
            "Image File": ""
        }

        if img and img.get("src"):
            img_path = download_image(img.get("src"), data["Product Name"])
            data["Image File"] = os.path.basename(img_path) if img_path else ""
            if img_path:
                image_files.append(img_path)

        return data

    except Exception as e:
        st.warning(f"Failed to scrape {url}: {str(e)}")
        return None

# --- INPUT ---
with st.form("scraper_inputs"):
    category_url = st.text_input(
        "Enter Product Category URL",
        "https://www.oscseeds.com/product-category/vegetables/",
        help="Example: https://www.oscseeds.com/product-category/flowers/"
    )
    check_btn = st.form_submit_button("\ud83d\udd0e Check Total Products")
    if check_btn:
        total, links = get_total_products_and_links(category_url)
        st.info(f"\ud83d\udd22 Total Products Found: {total}")
        st.session_state.links = links
        st.session_state.total = total

if 'links' in st.session_state:
    max_products = st.number_input("\ud83d\udd39 How many products to scrape?", min_value=1, max_value=st.session_state.total, value=min(10, st.session_state.total))

    if st.button("\u2b07\ufe0f Download Data & Images"):
        image_files = []
        all_products = []

        st.info(f"Scraping {max_products} products...")
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, link in enumerate(st.session_state.links[:max_products], 1):
            status_text.text(f"Scraping {i}/{max_products}...")
            data = scrape_product(link)
            if data:
                all_products.append(data)
            progress_bar.progress(i / max_products)
            sleep(REQUEST_DELAY)

        progress_bar.empty()
        status_text.empty()

        if not all_products:
            st.error("No data extracted.")
            st.stop()

        df = pd.DataFrame(all_products)
        excel_file = "osc_products.xlsx"
        df.to_excel(excel_file, index=False)

        col1, col2 = st.columns(2)
        with col1:
            with open(excel_file, "rb") as f:
                st.download_button("\ud83d\udcc5 Download Excel", f, file_name=excel_file)

        with col2:
            if image_files:
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for img_path in image_files:
                        zipf.write(img_path, os.path.basename(img_path))
                zip_buffer.seek(0)
                st.download_button("\ud83d\udcc1 Download Images (ZIP)", data=zip_buffer, file_name="osc_images.zip", mime="application/zip")
            else:
                st.warning("No images downloaded.")

# --- STYLING ---
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
    .stDataFrame {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)
