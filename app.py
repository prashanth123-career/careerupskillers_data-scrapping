import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import re
import zipfile
from io import BytesIO
from time import sleep, time
from urllib.parse import urlparse
from PIL import Image
from datetime import timedelta

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
    submit = st.form_submit_button("Analyze Website")

# --- WEBSITE ANALYSIS ---
if submit:
    if not category_url.startswith('https://www.oscseeds.com'):
        st.error("Please enter a valid OSCSeeds.com category URL")
        st.stop()

    with st.spinner("Analyzing website structure..."):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }

        try:
            # Get first page to analyze
            response = requests.get(category_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Count products on first page
            products_on_page = len(soup.select("li.product a.woocommerce-LoopProduct-link[href]"))
            
            # Estimate total pages by checking pagination
            page_links = soup.select("a.page-numbers:not(.next)")
            if page_links:
                try:
                    total_pages = max(int(link.text) for link in page_links if link.text.isdigit())
                except:
                    total_pages = 1
            else:
                total_pages = 1

            estimated_total_products = products_on_page * total_pages

            st.success(f"Website analysis complete!")
            st.markdown(f"""
            **Website Structure Found:**
            - Products per page: {products_on_page}
            - Total pages: {total_pages}
            - Estimated total products: {estimated_total_products}
            """)

            # Download options
            st.markdown("### Download Options")
            col1, col2 = st.columns(2)
            
            with col1:
                full_download = st.button("Download Full Dataset")
            
            with col2:
                page_by_page = st.button("Download Page by Page")

            if full_download or page_by_page:
                all_products = []
                image_files = []
                processed_pages = 0
                processed_products = 0
                start_time = time()

                # Progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                time_text = st.empty()
                results_container = st.empty()

                def get_product_links(base_url):
                    """Get all product links from paginated category"""
                    links = []
                    page = 1
                    while True:
                        url = f"{base_url}page/{page}/" if page > 1 else base_url
                        try:
                            resp = requests.get(url, headers=headers, timeout=10)
                            if resp.status_code == 404:
                                break
                            resp.raise_for_status()
                            
                            soup = BeautifulSoup(resp.text, 'html.parser')
                            products = soup.select("li.product a.woocommerce-LoopProduct-link[href]")
                            
                            if not products:
                                break
                                
                            for p in products:
                                link = p.get('href').split('?')[0]  # Remove query params
                                if link and link not in links:
                                    links.append(link)
                            
                            processed_pages = page
                            progress = processed_pages / total_pages
                            progress_bar.progress(min(progress, 1.0))
                            status_text.text(f"Found {len(links)} products from {processed_pages}/{total_pages} pages")
                            
                            if page_by_page and page > 1:  # For page-by-page mode
                                break
                                
                            page += 1
                            sleep(REQUEST_DELAY)
                        except Exception as e:
                            st.warning(f"Couldn't fetch page {page}: {str(e)}")
                            break
                    return links

                def download_image(img_url, product_name):
                    """Download product image with proper naming"""
                    try:
                        if not img_url.startswith('http'):
                            return ""
                            
                        response = requests.get(img_url, headers=headers, stream=True, timeout=15)
                        response.raise_for_status()
                        
                        # Create safe filename
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
                    """Scrape individual product details"""
                    try:
                        response = requests.get(url, headers=headers, timeout=10)
                        response.raise_for_status()
                        soup = BeautifulSoup(response.text, 'html.parser')

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

                # Main scraping loop
                links = get_product_links(category_url)
                
                for i, link in enumerate(links, 1):
                    elapsed = timedelta(seconds=int(time() - start_time))
                    time_text.text(f"Time elapsed: {elapsed}")
                    status_text.text(f"Processing product {i}/{len(links)}")
                    progress_bar.progress(i / len(links))
                    
                    product_data = scrape_product(link)
                    if product_data:
                        all_products.append(product_data)
                        processed_products += 1
                    
                    sleep(REQUEST_DELAY)

                    # For page-by-page mode, show intermediate results
                    if page_by_page and i % products_on_page == 0:
                        df = pd.DataFrame(all_products)
                        results_container.dataframe(df.tail(products_on_page))
                        st.session_state.current_page = i // products_on_page
                        break

                # Final processing
                progress_bar.empty()
                status_text.empty()
                time_text.empty()

                if not all_products:
                    st.error("No products were scraped.")
                    st.stop()

                # Save Excel
                df = pd.DataFrame(all_products)
                excel_file = "osc_seeds_data.xlsx"
                df.to_excel(excel_file, index=False)

                elapsed = timedelta(seconds=int(time() - start_time))
                st.success(f"✅ Successfully scraped {processed_products} products in {elapsed}")

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
                            for img_path in image_files:
                                zipf.write(img_path, os.path.basename(img_path))
                        zip_buffer.seek(0)
                        
                        st.download_button(
                            "📦 Download Images (ZIP)",
                            data=zip_buffer,
                            file_name="osc_seeds_images.zip",
                            mime="application/zip"
                        )
                    else:
                        st.warning("No images were downloaded")

        except Exception as e:
            st.error(f"Failed to analyze website: {str(e)}")

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
