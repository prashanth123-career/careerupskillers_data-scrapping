import os
import time
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import io
from io import BytesIO
import base64

# Streamlit App Config
st.set_page_config(page_title="OSC Seeds Scraper", page_icon="🌱")

# Constants
BASE_URL = "https://www.OSCseeds.com"
OUTPUT_FOLDER = "osc_seeds_data"
EXCEL_FILE = "osc_seeds_products.xlsx"
IMAGE_FOLDER = os.path.join(OUTPUT_FOLDER, "images")

# --- Helper Functions ---
def setup_driver():
    """Initialize Selenium WebDriver (headless Chrome)"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def create_output_folder():
    """Create folders for storing data & images"""
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(IMAGE_FOLDER, exist_ok=True)

def scrape_product_page(driver, url):
    """Scrape product details from a single page"""
    driver.get(url)
    time.sleep(2)  # Allow page to load
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    product_data = {
        'name': soup.find('h1').text.strip() if soup.find('h1') else 'N/A',
        'price': soup.find(class_='price').text.strip() if soup.find(class_='price') else 'N/A',
        'sku': soup.find(class_='sku').text.strip() if soup.find(class_='sku') else 'N/A',
        'description': soup.find(class_='description').text.strip() if soup.find(class_='description') else 'N/A',
        'image_url': soup.find('img', class_='product-image')['src'] if soup.find('img', class_='product-image') else None,
        'product_url': url
    }
    return product_data

def download_image(url, product_id):
    """Download and save product image"""
    if not url: return None
    try:
        response = requests.get(url if url.startswith('http') else BASE_URL + url)
        if response.status_code == 200:
            img_path = os.path.join(IMAGE_FOLDER, f"{product_id}.jpg")
            with open(img_path, 'wb') as f:
                f.write(response.content)
            return img_path
    except Exception as e:
        st.warning(f"Failed to download image: {e}")
    return None

def get_image_download_link(img_path):
    """Generate download link for Streamlit"""
    with open(img_path, "rb") as f:
        img_bytes = f.read()
    b64 = base64.b64encode(img_bytes).decode()
    return f'<a href="data:image/jpeg;base64,{b64}" download="{os.path.basename(img_path)}">Download Image</a>'

# --- Streamlit UI ---
st.title("🌱 OSC Seeds Product Scraper")
st.markdown("Extract product data & images from OSCseeds.com")

with st.form("scraper_form"):
    st.write("### Scraping Options")
    category = st.selectbox("Select Category", ["Vegetables", "Flowers", "Herbs"])
    max_products = st.slider("Max Products to Scrape", 1, 100, 10)
    submit = st.form_submit_button("Start Scraping")

if submit:
    st.info(f"Scraping {max_products} {category} products...")
    
    # Initialize
    create_output_folder()
    driver = setup_driver()
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Simulate finding product URLs (replace with actual scraping)
        product_urls = [f"{BASE_URL}/{category.lower()}/{i}" for i in range(1, max_products+1)]
        
        # Scrape each product
        all_products = []
        for i, url in enumerate(product_urls, 1):
            status_text.text(f"Processing product {i}/{len(product_urls)}...")
            progress_bar.progress(i/len(product_urls))
            
            product_data = scrape_product_page(driver, url)
            if product_data['image_url']:
                product_data['image_path'] = download_image(product_data['image_url'], product_data['sku'] or f"product_{i}")
            all_products.append(product_data)
        
        # Save to Excel
        df = pd.DataFrame(all_products)
        excel_path = os.path.join(OUTPUT_FOLDER, EXCEL_FILE)
        df.to_excel(excel_path, index=False)
        
        # Show results
        st.success("Scraping completed successfully!")
        st.dataframe(df.head())
        
        # Download buttons
        with open(excel_path, "rb") as f:
            st.download_button("Download Excel", f, file_name=EXCEL_FILE)
        
        if 'image_path' in df.columns:
            st.write("### Sample Images")
            cols = st.columns(3)
            for idx, row in df.head(3).iterrows():
                if row['image_path'] and os.path.exists(row['image_path']):
                    cols[idx%3].image(row['image_path'], width=150)
                    cols[idx%3].markdown(get_image_download_link(row['image_path']), unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
    finally:
        driver.quit()
        progress_bar.empty()
