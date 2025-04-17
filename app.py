import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from io import BytesIO
import re

# Streamlit App Config
st.set_page_config(page_title="OSC Seeds Scraper", layout="wide")

def get_valid_urls():
    """Returns actual working category URLs from OSCseeds.com"""
    return {
        "Vegetables": "https://www.oscseeds.com/category/vegetable-seeds/",
        "Flowers": "https://www.oscseeds.com/category/flower-seeds/",
        "Herbs": "https://www.oscseeds.com/category/herb-seeds/",
        "All Products": "https://www.oscseeds.com/product-category/all-products/"
    }

def scrape_osc_seeds(url, max_products=10):
    """Main scraping function for OSCseeds.com"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # First get the category page
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find product links - updated for OSCseeds structure
        product_links = []
        for product in soup.select('div.product-grid-item a.woocommerce-LoopProduct-link'):
            href = product.get('href')
            if href and '/product/' in href:
                product_links.append(href)
                if len(product_links) >= max_products:
                    break
        
        if not product_links:
            return None, "No products found on this page"
        
        # Scrape each product
        all_products = []
        for i, product_url in enumerate(product_links):
            try:
                # Respectful delay between requests
                time.sleep(1)
                
                product_response = requests.get(product_url, headers=headers)
                product_response.raise_for_status()
                product_soup = BeautifulSoup(product_response.text, 'html.parser')
                
                # Extract product data - updated selectors for OSCseeds
                product_data = {
                    'name': product_soup.find('h1', class_='product_title').get_text(strip=True) if product_soup.find('h1', class_='product_title') else 'N/A',
                    'price': product_soup.find('p', class_='price').get_text(strip=True) if product_soup.find('p', class_='price') else 'N/A',
                    'sku': product_soup.find('span', class_='sku').get_text(strip=True) if product_soup.find('span', class_='sku') else 'N/A',
                    'description': product_soup.find('div', class_='woocommerce-product-details__short-description').get_text(strip=True) if product_soup.find('div', class_='woocommerce-product-details__short-description') else 'N/A',
                    'category': url.split('/')[-2].replace('-', ' ').title(),
                    'product_url': product_url
                }
                
                # Extract specifications from tabs
                specs = {}
                tab_content = product_soup.find('div', class_='woocommerce-Tabs-panel')
                if tab_content:
                    for row in tab_content.find_all('tr'):
                        cols = row.find_all('td')
                        if len(cols) == 2:
                            key = cols[0].get_text(strip=True)
                            value = cols[1].get_text(strip=True)
                            specs[key] = value
                
                product_data['specifications'] = specs
                all_products.append(product_data)
                
            except Exception as e:
                st.warning(f"Couldn't scrape product {product_url}: {str(e)}")
                continue
        
        return pd.DataFrame(all_products), None
    
    except Exception as e:
        return None, str(e)

# Streamlit UI
st.title("🌱 OSC Seeds Scraper (Working Version)")
st.markdown("""
This version is specifically adapted for OSCseeds.com's actual structure.
Select a category from the dropdown below.
""")

# Get valid URLs
valid_urls = get_valid_urls()

with st.form("scraper_form"):
    col1, col2 = st.columns(2)
    with col1:
        category = st.selectbox("Select Category", list(valid_urls.keys()))
    with col2:
        max_products = st.slider("Maximum products", 1, 50, 10)
    
    if st.form_submit_button("Start Scraping"):
        with st.spinner(f"Scraping {category} products..."):
            url = valid_urls[category]
            df, error = scrape_osc_seeds(url, max_products)
            
            if error:
                st.error(f"Error: {error}")
            elif df is None:
                st.warning("No products found. The website structure may have changed.")
            else:
                st.success(f"Successfully scraped {len(df)} products!")
                
                # Show data
                st.dataframe(df)
                
                # Export
                excel_buffer = BytesIO()
                df.to_excel(excel_buffer, index=False)
                st.download_button(
                    label="Download Excel",
                    data=excel_buffer.getvalue(),
                    file_name=f"osc_seeds_{category.lower()}.xlsx",
                    mime="application/vnd.ms-excel"
                )

# Add CSS to make wider
st.markdown("""
<style>
    .main .block-container {
        max-width: 1200px;
    }
    .stDataFrame {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)
