import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from io import BytesIO
from PIL import Image
import base64
import zipfile

# Streamlit App Config
st.set_page_config(page_title="OSC Seeds Scraper", page_icon="🌱", layout="wide")

def scrape_product_page(url):
    """Scrape individual product page for details"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract product details - UPDATE THESE SELECTORS
        product_data = {
            'name': soup.select_one('h1.product-title').get_text(strip=True) if soup.select_one('h1.product-title') else 'N/A',
            'price': soup.select_one('span.price').get_text(strip=True) if soup.select_one('span.price') else 'N/A',
            'sku': soup.select_one('span.sku').get_text(strip=True) if soup.select_one('span.sku') else 'N/A',
            'description': soup.select_one('div.product-description').get_text(strip=True) if soup.select_one('div.product-description') else 'N/A',
            'category': soup.select_one('span.category').get_text(strip=True) if soup.select_one('span.category') else 'N/A',
            'specifications': {},
            'image_url': soup.select_one('img.product-image')['src'] if soup.select_one('img.product-image') else None,
            'product_url': url
        }
        
        # Extract specifications
        for row in soup.select('table.specifications tr'):
            cells = row.select('td')
            if len(cells) == 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                product_data['specifications'][key] = value
        
        return product_data
    
    except Exception as e:
        st.error(f"Error scraping product page: {str(e)}")
        return None

def scrape_category_page(url):
    """Scrape category page to get product links"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get all product links - UPDATE THIS SELECTOR
        return [
            a['href'] if a['href'].startswith('http') else f"https://www.OSCseeds.com{a['href']}"
            for a in soup.select('a.product-link')
            if '/product/' in a['href']
        ][:50]  # Limit to 50 products for demo
    
    except Exception as e:
        st.error(f"Error scraping category page: {str(e)}")
        return []

def download_image(url, product_id, image_folder):
    """Download and save product image"""
    try:
        if not url: return None
        
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        
        img_path = f"{image_folder}/{product_id}.jpg"
        with open(img_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        return img_path
    except Exception as e:
        st.warning(f"Couldn't download image for {product_id}: {str(e)}")
        return None

def create_zip(files, zip_name):
    """Create ZIP file from list of files"""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in files:
            if file and os.path.exists(file):
                zipf.write(file, os.path.basename(file))
    zip_buffer.seek(0)
    return zip_buffer

# Streamlit UI
st.title("🌱 OSC Seeds Complete Scraper")
st.write("Extract all seed data with specifications and images")

with st.form("scraper_form"):
    url = st.text_input("Enter OSCseeds.com category URL", "https://www.OSCseeds.com/vegetables")
    max_products = st.slider("Maximum products to scrape", 1, 100, 20)
    submit = st.form_submit_button("Start Scraping")

if submit:
    with st.spinner("Scraping in progress..."):
        try:
            # Setup folders
            image_folder = "osc_seed_images"
            os.makedirs(image_folder, exist_ok=True)
            
            # Get product links
            product_links = scrape_category_page(url)[:max_products]
            
            if not product_links:
                st.warning("No products found. Check the URL or website structure.")
                st.stop()
            
            # Scrape each product
            all_products = []
            image_paths = []
            progress_bar = st.progress(0)
            
            for i, product_url in enumerate(product_links):
                progress_bar.progress((i + 1) / len(product_links))
                
                product_data = scrape_product_page(product_url)
                if product_data:
                    # Download image
                    img_path = download_image(
                        product_data['image_url'],
                        product_data['sku'] or f"product_{i}",
                        image_folder
                    )
                    if img_path:
                        product_data['image_filename'] = os.path.basename(img_path)
                        image_paths.append(img_path)
                    
                    all_products.append(product_data)
            
            if all_products:
                # Create DataFrame
                df = pd.DataFrame(all_products)
                
                # Flatten specifications
                specs_df = pd.json_normalize(df['specifications'])
                df = pd.concat([df.drop(['specifications', 'image_url'], axis=1), specs_df], axis=1)
                
                st.success(f"✅ Successfully scraped {len(df)} products!")
                
                # Show data
                st.subheader("Product Data Preview")
                st.dataframe(df.head())
                
                # Export section
                st.subheader("Download Data")
                col1, col2 = st.columns(2)
                
                with col1:
                    # Excel Export
                    excel_buffer = BytesIO()
                    df.to_excel(excel_buffer, index=False)
                    st.download_button(
                        label="Download Excel (All Data)",
                        data=excel_buffer.getvalue(),
                        file_name="osc_seeds_data.xlsx",
                        mime="application/vnd.ms-excel"
                    )
                
                with col2:
                    # Images ZIP Export
                    if image_paths:
                        zip_buffer = create_zip(image_paths, "osc_seed_images.zip")
                        st.download_button(
                            label="Download Images (ZIP)",
                            data=zip_buffer.getvalue(),
                            file_name="osc_seed_images.zip",
                            mime="application/zip"
                        )
                    else:
                        st.warning("No images were downloaded")
                
                # Cleanup
                for img in image_paths:
                    try:
                        os.remove(img)
                    except:
                        pass
            
        except Exception as e:
            st.error(f"🚨 An error occurred: {str(e)}")
            st.exception(e)

# Add CSS styling
st.markdown("""
<style>
    .main .block-container {
        max-width: 1200px;
    }
    .stDownloadButton button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)
