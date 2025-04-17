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
REQUEST_DELAY = 1.5  # seconds between requests
IMAGE_FOLDER = "seed_images"
os.makedirs(IMAGE_FOLDER, exist_ok=True)

# --- STREAMLIT UI ---
st.set_page_config(page_title="🌱 OSC Seeds Scraper", layout="centered")
st.title("🌱 OSC Seeds Product Scraper")
st.markdown("Extract product data from [OSCSeeds.com](https://www.oscseeds.com)")

# --- INPUTS ---
with st.form("scraper_inputs"):
    category_url = st.text_input(
        "Enter Product Category URL",
        "https://www.oscseeds.com/product-category/vegetables/",
        help="Example: https://www.oscseeds.com/product-category/flowers/"
    )
    max_products = st.slider("Number of products to extract", 1, 100, 10)
    submit = st.form_submit_button("Start Scraping")

# --- MAIN SCRAPING LOGIC ---
if submit:
    if not category_url.startswith('https://www.oscseeds.com'):
        st.error("Please enter a valid OSCSeeds.com category URL")
        st.stop()

    with st.spinner(f"Scraping {max_products} products..."):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.oscseeds.com/'
        }

        all_products = []
        image_files = []

        # --- IMPROVED FUNCTIONS ---
        def get_product_links(base_url, limit):
            """Get product links with better error handling and duplicate prevention"""
            links = []
            page = 1
            seen_links = set()
            
            while len(links) < limit:
                url = f"{base_url}page/{page}/" if page > 1 else base_url
                try:
                    resp = requests.get(url, headers=headers, timeout=10)
                    resp.raise_for_status()
                    
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    products = soup.select("li.product a.woocommerce-LoopProduct-link[href]")
                    
                    if not products:
                        break
                        
                    for p in products:
                        link = p.get('href').split('?')[0]  # Remove query params
                        if link and link not in seen_links:
                            seen_links.add(link)
                            links.append(link)
                            if len(links) >= limit:
                                break
                    
                    page += 1
                    sleep(REQUEST_DELAY)
                except requests.exceptions.RequestException as e:
                    st.warning(f"Couldn't fetch page {page}: {str(e)}")
                    break
                    
            return links[:limit]

        def download_image(img_url, product_name):
            """Improved image download with proper naming and error handling"""
            try:
                if not img_url.startswith('http'):
                    return ""
                    
                response = requests.get(img_url, headers=headers, stream=True, timeout=15)
                response.raise_for_status()
                
                # Create safe filename from product name
                safe_name = re.sub(r'[^\w\-_\. ]', '_', product_name)[:50]
                ext = os.path.splitext(urlparse(img_url).path)[1][:4] or '.jpg'
                filename = f"{safe_name}{ext}"
                filepath = os.path.join(IMAGE_FOLDER, filename)
                
                # Save image with PIL for better format handling
                with Image.open(BytesIO(response.content)) as img:
                    img.save(filepath)
                
                return filepath
            except Exception as e:
                st.warning(f"Couldn't download image for {product_name}: {str(e)}")
                return ""

        def scrape_product(url):
            """Enhanced product scraping with multiple fallback selectors"""
            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # Multiple fallback selectors for each field
                name = (soup.select_one("h1.product_title") or 
                       soup.select_one("h1.entry-title")).get_text(strip=True)
                
                price = (soup.select_one("p.price") or 
                        soup.select_one("span.woocommerce-Price-amount")).get_text(strip=True)
                
                desc = (soup.select_one("div.woocommerce-product-details__short-description") or 
                       soup.select_one("div.product_meta") or 
                       soup.select_one("div.product_description")).get_text(" ", strip=True)
                
                img = (soup.select_one("div.woocommerce-product-gallery__image img") or 
                      soup.select_one("img.wp-post-image") or 
                      soup.select_one("img.attachment-woocommerce_single"))

                data = {
                    "Product Name": name if name else "N/A",
                    "Price": re.sub(r'\s+', ' ', price).strip() if price else "N/A",
                    "Description": desc if desc else "N/A",
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

        # --- EXECUTION WITH PROGRESS ---
        links = get_product_links(category_url, max_products)
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, link in enumerate(links, 1):
            status_text.text(f"Processing {i}/{len(links)}: {link[:50]}...")
            progress_bar.progress(i / len(links))
            
            product_data = scrape_product(link)
            if product_data:
                all_products.append(product_data)
            
            sleep(REQUEST_DELAY)

        progress_bar.empty()
        status_text.empty()

        if not all_products:
            st.error("No products were scraped. The website structure may have changed.")
            st.stop()

        # --- DATA EXPORT ---
        df = pd.DataFrame(all_products)
        excel_file = "osc_seeds_data.xlsx"
        df.to_excel(excel_file, index=False)

        # --- RESULTS DISPLAY ---
        st.success(f"✅ Successfully scraped {len(df)} products!")
        
        with st.expander("View Scraped Data"):
            st.dataframe(df)

        # --- DOWNLOAD BUTTONS ---
        col1, col2 = st.columns(2)
        
        with col1:
            with open(excel_file, "rb") as f:
                st.download_button(
                    "📥 Download Excel",
                    f,
                    file_name=excel_file,
                    mime="application/vnd.ms-excel",
                    help="Contains all product data including descriptions"
                )
        
        with col2:
            if image_files:
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for img_path in image_files:
                        zipf.write(img_path, os.path.basename(img_path))
                zip_buffer.seek(0)
                
                st.download_button(
                    "📦 Download Images (ZIP)",
                    data=zip_buffer,
                    file_name="osc_seeds_images.zip",
                    mime="application/zip",
                    help="Contains all product images with proper filenames"
                )
            else:
                st.warning("No images were downloaded. The website may be blocking image downloads.")

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
    [data-testid="stExpander"] .st-emotion-cache-1q7spjk {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)
