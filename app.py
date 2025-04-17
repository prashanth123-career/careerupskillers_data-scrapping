import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from io import BytesIO
from PIL import Image
import base64

# Streamlit App Config
st.set_page_config(page_title="OSC Seeds Scraper", page_icon="🌱", layout="wide")

def scrape_product_page(url):
    """Scrape individual product page for details"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract product details - ADAPT THESE SELECTORS TO OSCseeds.com's ACTUAL HTML
        product_data = {
            'name': soup.select_one('h1.product-title').get_text(strip=True) if soup.select_one('h1.product-title') else 'N/A',
            'price': soup.select_one('span.price').get_text(strip=True) if soup.select_one('span.price') else 'N/A',
            'sku': soup.select_one('span.sku').get_text(strip=True) if soup.select_one('span.sku') else 'N/A',
            'description': soup.select_one('div.product-description').get_text(strip=True) if soup.select_one('div.product-description') else 'N/A',
            'specifications': {},
            'image_url': soup.select_one('img.product-image')['src'] if soup.select_one('img.product-image') else None,
            'product_url': url
        }
        
        # Extract specifications table if exists
        specs_table = soup.select('table.specifications tr')
        for row in specs_table:
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
        
        # Get all product links - ADAPT THIS SELECTOR
        product_links = []
        for link in soup.select('a.product-link'):
            href = link.get('href')
            if href and '/product/' in href:
                product_links.append(href if href.startswith('http') else f"https://www.OSCseeds.com{href}")
        
        return product_links
    
    except Exception as e:
        st.error(f"Error scraping category page: {str(e)}")
        return []

def download_image(url, product_id):
    """Download and save product image"""
    try:
        if not url:
            return None
            
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        
        img = Image.open(BytesIO(response.content))
        img_path = f"product_images/{product_id}.jpg"
        os.makedirs("product_images", exist_ok=True)
        img.save(img_path)
        return img_path
    except Exception as e:
        st.warning(f"Couldn't download image: {str(e)}")
        return None

def get_image_download_link(img_path):
    """Generate download link for image"""
    with open(img_path, "rb") as f:
        img_bytes = f.read()
    b64 = base64.b64encode(img_bytes).decode()
    return f'<a href="data:image/jpeg;base64,{b64}" download="{os.path.basename(img_path)}">Download Image</a>'

# Streamlit UI
st.title("🌱 OSC Seeds Product Scraper")
st.write("Extract product specs, pricing, and images from OSCseeds.com")

with st.form("scraper_form"):
    url = st.text_input("Enter OSCseeds.com category URL", "https://www.OSCseeds.com/vegetables")
    submit = st.form_submit_button("Start Scraping")

if submit:
    with st.spinner("Scraping in progress..."):
        try:
            # Get all product links from category page
            product_links = scrape_category_page(url)
            
            if not product_links:
                st.warning("No products found. Check the URL or website structure.")
                st.stop()
            
            # Scrape each product
            all_products = []
            progress_bar = st.progress(0)
            
            for i, product_url in enumerate(product_links[:10]):  # Limit to 10 products for demo
                progress_bar.progress((i + 1) / min(10, len(product_links)))
                
                product_data = scrape_product_page(product_url)
                if product_data:
                    # Download image if available
                    if product_data['image_url']:
                        product_data['image_path'] = download_image(
                            product_data['image_url'],
                            product_data['sku'] or f"product_{i}"
                        )
                    all_products.append(product_data)
            
            if all_products:
                # Convert to DataFrame
                df = pd.DataFrame(all_products)
                
                # Flatten specifications into columns
                specs_df = pd.json_normalize(df['specifications'])
                df = pd.concat([df.drop(['specifications'], axis=1), specs_df], axis=1)
                
                st.success(f"Successfully scraped {len(df)} products!")
                
                # Show data preview
                st.subheader("Product Data Preview")
                st.dataframe(df.head())
                
                # Export options
                st.subheader("Export Data")
                
                # Excel Export
                excel_buffer = BytesIO()
                df.to_excel(excel_buffer, index=False)
                st.download_button(
                    label="Download Excel with All Data",
                    data=excel_buffer.getvalue(),
                    file_name="osc_products.xlsx",
                    mime="application/vnd.ms-excel"
                )
                
                # Show sample images
                if 'image_path' in df.columns:
                    st.subheader("Sample Product Images")
                    cols = st.columns(3)
                    for idx, row in df.head(3).iterrows():
                        if row['image_path'] and os.path.exists(row['image_path']):
                            cols[idx%3].image(row['image_path'], width=200)
                            cols[idx%3].markdown(get_image_download_link(row['image_path']), unsafe_allow_html=True)
            
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

# Add CSS to make wider
st.markdown("""
<style>
    .main .block-container {
        max-width: 1200px;
    }
</style>
""", unsafe_allow_html=True)
