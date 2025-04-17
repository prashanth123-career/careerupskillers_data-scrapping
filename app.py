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
st.markdown("Extract product data from [OSCSeeds.com](https://www.oscseeds.com)")

# --- INPUT ---
category_url = st.text_input(
    "Enter Product Category URL",
    "https://www.oscseeds.com/product-category/vegetables/"
)
max_products = st.slider("How many products to extract?", 1, 100, 10)

# --- MAIN FUNCTION ---
if st.button("Start Scraping"):
    if not category_url.startswith('https://www.oscseeds.com'):
        st.error("Please enter a valid OSCSeeds.com category URL")
        st.stop()

    with st.spinner("Scraping in progress..."):
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept-Language': 'en-US,en;q=0.9'
        }

        all_products = []
        image_files = []

        def get_product_links(base_url, limit):
            links = []
            page = 1
            while len(links) < limit:
                url = f"{base_url}page/{page}/" if page > 1 else base_url
                try:
                    resp = requests.get(url, headers=headers)
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    products = soup.select("li.product a.woocommerce-LoopProduct-link")
                    if not products:
                        break
                    for p in products:
                        link = p.get('href')
                        if link and link not in links:
                            links.append(link)
                        if len(links) >= limit:
                            break
                    page += 1
                    sleep(REQUEST_DELAY)
                except:
                    break
            return links

        def download_image(img_url):
            try:
                r = requests.get(img_url, headers=headers, stream=True)
                if r.status_code == 200:
                    filename = os.path.basename(urlparse(img_url).path)
                    filepath = os.path.join(IMAGE_FOLDER, filename)
                    with open(filepath, 'wb') as f:
                        f.write(r.content)
                    return filepath
            except:
                pass
            return ""

        def scrape_product(url):
            try:
                r = requests.get(url, headers=headers)
                soup = BeautifulSoup(r.text, 'html.parser')

                name = soup.select_one("h1.product_title")
                price = soup.select_one("p.price")
                desc = soup.select_one("div.woocommerce-product-details__short-description")
                img = soup.select_one("div.woocommerce-product-gallery__image img")

                data = {
                    "Product Name": name.get_text(strip=True) if name else "N/A",
                    "Price": price.get_text(strip=True) if price else "N/A",
                    "Description": desc.get_text(strip=True) if desc else "N/A",
                    "Product URL": url,
                    "Image File": ""
                }

                if img and img.get("src"):
                    img_path = download_image(img.get("src"))
                    data["Image File"] = os.path.basename(img_path) if img_path else ""

                    if img_path:
                        image_files.append(img_path)

                return data

            except Exception as e:
                st.warning(f"Failed: {url} - {e}")
                return None

        # --- EXECUTION ---
        links = get_product_links(category_url, max_products)
        progress = st.progress(0)
        status = st.empty()

        for i, link in enumerate(links, 1):
            status.text(f"Scraping {i}/{len(links)}...")
            progress.progress(i / len(links))
            pdata = scrape_product(link)
            if pdata:
                all_products.append(pdata)
            sleep(REQUEST_DELAY)

        progress.empty()
        status.empty()

        if not all_products:
            st.error("No products scraped.")
            st.stop()

        # Save Excel
        df = pd.DataFrame(all_products)
        excel_file = "osc_seeds_data.xlsx"
        df.to_excel(excel_file, index=False)

        # --- DOWNLOADS ---
        st.success(f"✅ Scraped {len(df)} products")

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
                st.warning("No images were downloaded")

# --- STYLING ---
st.markdown("""
<style>
    .stDownloadButton button { width: 100%; }
    .stSpinner > div { justify-content: center; }
</style>
""", unsafe_allow_html=True)
