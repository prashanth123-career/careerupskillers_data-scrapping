import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import re
import zipfile
from io import BytesIO
from time import sleep
from urllib.parse import urlparse, urljoin

# Configuration
REQUEST_DELAY = 1.5  # seconds between requests
IMAGE_FOLDER = "seed_images"
os.makedirs(IMAGE_FOLDER, exist_ok=True)

# Set page config
st.set_page_config(page_title="OSC Seeds Scraper", page_icon="🌱", layout="centered")

# Header
st.title("🌱 OSC Seeds Product Scraper")
st.markdown("Extract product data from [OSCSeeds.com](https://www.oscseeds.com)")

# Input category URL
category_url = st.text_input(
    "Enter Product Category URL",
    "https://www.oscseeds.com/product-category/vegetables/"
)

if st.button("Start Scraping"):
    if not category_url.startswith('https://www.oscseeds.com'):
        st.error("Please enter a valid OSCSeeds.com category URL")
        st.stop()

    with st.spinner("Scraping in progress... please wait."):
        # Initialize
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        all_products = []
        image_files = []

        def get_product_links(base_url):
            """Collect all product links from paginated category"""
            links = []
            page = 1
            while True:
                url = f"{base_url}page/{page}/" if page > 1 else base_url
                try:
                    response = requests.get(url, headers=headers)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    products = soup.select("li.product a.woocommerce-LoopProduct-link")
                    if not products:
                        break
                        
                    for product in products:
                        href = product.get('href')
                        if href and href not in links:
                            links.append(href)
                    
                    page += 1
                    sleep(REQUEST_DELAY)
                except Exception as e:
                    st.warning(f"Couldn't fetch page {page}: {str(e)}")
                    break
            return links

        def scrape_product_page(url):
            """Scrape individual product details"""
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract data
                data = {
                    "Product Name": soup.select_one("h1.product_title").get_text(strip=True) if soup.select_one("h1.product_title") else "N/A",
                    "Description": (soup.select_one("div.woocommerce-product-details__short-description").get_text(strip=True) 
                                  if soup.select_one("div.woocommerce-product-details__short-description") else "N/A"),
                    "Price": soup.select_one("p.price").get_text(strip=True) if soup.select_one("p.price") else "N/A",
                    "Product URL": url,
                    "Image File": ""
                }

                # Handle image
                img_tag = soup.select_one("figure.woocommerce-product-gallery__wrapper img")
                if img_tag and 'src' in img_tag.attrs:
                    img_url = img_tag['src']
                    if img_url.startswith('http'):
                        img_path = download_image(img_url, IMAGE_FOLDER)
                        if img_path:
                            data["Image File"] = os.path.basename(img_path)
                            image_files.append(img_path)

                return data
            except Exception as e:
                st.warning(f"Failed to scrape {url}: {str(e)}")
                return None

        def download_image(url, folder):
            """Download and save product image"""
            try:
                response = requests.get(url, headers=headers, stream=True, timeout=10)
                response.raise_for_status()
                
                filename = os.path.join(folder, os.path.basename(urlparse(url).path))
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return filename
            except Exception as e:
                st.warning(f"Image download failed: {str(e)}")
                return None

        # Main execution
        product_links = get_product_links(category_url)
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, link in enumerate(product_links, 1):
            status_text.text(f"Processing product {i}/{len(product_links)}")
            progress_bar.progress(i/len(product_links))
            
            product_data = scrape_product_page(link)
            if product_data:
                all_products.append(product_data)
            
            sleep(REQUEST_DELAY)

        progress_bar.empty()
        status_text.empty()

        if not all_products:
            st.error("No products found. Check the URL or website structure.")
            st.stop()

        # Save and display results
        df = pd.DataFrame(all_products)
        excel_file = "osc_seeds_data.xlsx"
        df.to_excel(excel_file, index=False)

        st.success(f"✅ Successfully scraped {len(df)} products!")
        
        # Download buttons
        col1, col2 = st.columns(2)
        
        with col1:
            with open(excel_file, "rb") as f:
                st.download_button(
                    "📥 Download Excel",
                    f,
                    file_name=excel_file,
                    mime="application/vnd.ms-excel"
                )
        
        with col2:
            if image_files:
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for img in image_files:
                        zipf.write(img, os.path.basename(img))
                zip_buffer.seek(0)
                
                st.download_button(
                    "📦 Download Images (ZIP)",
                    data=zip_buffer,
                    file_name="osc_seeds_images.zip",
                    mime="application/zip"
                )
            else:
                st.warning("No images were downloaded")

# Add some styling
st.markdown("""
<style>
    .stDownloadButton button {
        width: 100%;
    }
    .stSpinner > div {
        justify-content: center;
    }
</style>
""", unsafe_allow_html=True)
