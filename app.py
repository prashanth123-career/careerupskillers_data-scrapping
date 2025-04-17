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
from PIL import Image

# Configuration
REQUEST_DELAY = 2.0  # Increased delay to avoid blocking
IMAGE_FOLDER = "seed_images"
os.makedirs(IMAGE_FOLDER, exist_ok=True)

# Set page config
st.set_page_config(page_title="OSC Seeds Scraper", page_icon="🌱", layout="centered")

# Header
st.title("🌱 OSC Seeds Product Scraper")
st.markdown("Extract product data from [OSCSeeds.com](https://www.oscseeds.com)")

# User inputs
col1, col2 = st.columns(2)
with col1:
    category_url = st.text_input(
        "Enter Product Category URL",
        "https://www.oscseeds.com/product-category/vegetables/"
    )
with col2:
    max_products = st.number_input("Number of products to extract", min_value=1, max_value=100, value=10)

if st.button("Start Scraping"):
    if not category_url.startswith('https://www.oscseeds.com'):
        st.error("Please enter a valid OSCSeeds.com category URL")
        st.stop()

    with st.spinner(f"Scraping {max_products} products... please wait."):
        # Initialize
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.oscseeds.com/'
        }
        all_products = []
        image_files = []

        def get_product_links(base_url, max_links):
            """Collect product links with improved selectors"""
            links = []
            page = 1
            while len(links) < max_links:
                url = f"{base_url}page/{page}/" if page > 1 else base_url
                try:
                    response = requests.get(url, headers=headers)
                    if response.status_code == 404:
                        break
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Updated selectors for OSCSeeds
                    products = soup.select("li.product a:has(h2.woocommerce-loop-product__title)")
                    if not products:
                        break
                        
                    for product in products:
                        href = product.get('href')
                        if href and href not in links:
                            links.append(href)
                            if len(links) >= max_links:
                                break
                    
                    page += 1
                    sleep(REQUEST_DELAY)
                except Exception as e:
                    st.warning(f"Couldn't fetch page {page}: {str(e)}")
                    break
            return links[:max_links]

        def scrape_product_page(url):
            """Enhanced product scraping with better selectors"""
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                # Extract basic info with improved selectors
                product_name = soup.find("h1", class_="product_title").get_text(strip=True) if soup.find("h1", class_="product_title") else "N/A"
                
                # Get description from multiple possible locations
                description = ""
                desc_element = soup.find("div", class_="woocommerce-product-details__short-description") or \
                             soup.find("div", class_="product_meta") or \
                             soup.find("div", class_="product_description")
                if desc_element:
                    description = desc_element.get_text(" ", strip=True)
                
                price_element = soup.find("p", class_="price") or soup.find("span", class_="woocommerce-Price-amount")
                price = price_element.get_text(strip=True) if price_element else "N/A"
                
                # Clean price format
                price = re.sub(r'\s+', ' ', price).strip()

                # Image handling with multiple fallbacks
                img_url = None
                img_element = soup.find("img", class_="wp-post-image") or \
                            soup.find("img", class_="attachment-woocommerce_single") or \
                            soup.find("div", class_="woocommerce-product-gallery__image").find("img") if soup.find("div", class_="woocommerce-product-gallery__image") else None
                
                if img_element and 'src' in img_element.attrs:
                    img_url = img_element['src']
                
                # Download image
                img_filename = ""
                if img_url and img_url.startswith('http'):
                    img_path = download_image(img_url, IMAGE_FOLDER, product_name)
                    if img_path:
                        img_filename = os.path.basename(img_path)
                        image_files.append(img_path)

                return {
                    "Product Name": product_name,
                    "Description": description if description else "N/A",
                    "Price": price,
                    "Product URL": url,
                    "Image File": img_filename
                }
            except Exception as e:
                st.warning(f"Failed to scrape {url}: {str(e)}")
                return None

        def download_image(url, folder, product_name):
            """Improved image download with proper naming"""
            try:
                response = requests.get(url, headers=headers, stream=True, timeout=15)
                response.raise_for_status()
                
                # Create safe filename from product name
                safe_name = re.sub(r'[^\w\-_\. ]', '_', product_name)[:100]
                ext = os.path.splitext(urlparse(url).path)[1][:4] or '.jpg'
                filename = f"{safe_name}{ext}"
                filepath = os.path.join(folder, filename)
                
                with Image.open(BytesIO(response.content)) as img:
                    img.save(filepath)
                
                return filepath
            except Exception as e:
                st.warning(f"Image download failed for {product_name}: {str(e)}")
                return None

        # Main execution
        product_links = get_product_links(category_url, max_products)
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, link in enumerate(product_links, 1):
            status_text.text(f"Processing product {i}/{len(product_links)}: {link[:60]}...")
            progress_bar.progress(i/len(product_links))
            
            product_data = scrape_product_page(link)
            if product_data:
                all_products.append(product_data)
            
            sleep(REQUEST_DELAY)

        progress_bar.empty()
        status_text.empty()

        if not all_products:
            st.error("No products found. The website structure may have changed.")
            st.stop()

        # Save and display results
        df = pd.DataFrame(all_products)
        excel_file = "osc_seeds_data.xlsx"
        df.to_excel(excel_file, index=False)

        st.success(f"✅ Successfully scraped {len(df)} products!")
        st.dataframe(df)  # Show preview of the data
        
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
                st.warning("No images were downloaded. The website may be blocking image downloads.")

# Add some styling
st.markdown("""
<style>
    .stDownloadButton button {
        width: 100%;
    }
    .stSpinner > div {
        justify-content: center;
    }
    .stDataFrame {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)
