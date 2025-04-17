import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
from urllib.parse import urljoin
from time import sleep

# Set page config
st.set_page_config(page_title="OSC Seeds Scraper", page_icon="🌱", layout="centered")

# Output folder
IMAGE_FOLDER = "seed_images"
os.makedirs(IMAGE_FOLDER, exist_ok=True)

# Header
st.title("🌱 OSC Seeds Product Scraper")
st.markdown("Extract product name, description, price, and images from [OSCSeeds.com](https://www.oscseeds.com).")

# Input category URL
category_url = st.text_input("Enter Product Category URL (e.g., vegetables)", "https://www.oscseeds.com/product-category/vegetables/")

if st.button("Start Scraping"):
    with st.spinner("Scraping in progress... please wait."):
        all_products = []

        def get_product_links(category_url):
            product_links = []
            page = 1
            while True:
                url = f"{category_url}page/{page}/"
                response = requests.get(url)
                if response.status_code != 200:
                    break

                soup = BeautifulSoup(response.text, 'html.parser')
                products = soup.select("li.product a.woocommerce-LoopProduct-link")
                if not products:
                    break

                for prod in products:
                    link = prod.get('href')
                    if link and link not in product_links:
                        product_links.append(link)

                page += 1
                sleep(0.5)

            return product_links

        def scrape_product_page(url):
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')

            title = soup.select_one("h1.product_title").get_text(strip=True) if soup.select_one("h1.product_title") else "N/A"
            description = soup.select_one("div.woocommerce-product-details__short-description")
            desc_text = description.get_text(strip=True) if description else "N/A"

            price = soup.select_one("p.price").get_text(strip=True) if soup.select_one("p.price") else "N/A"

            img_tag = soup.select_one("figure.woocommerce-product-gallery__wrapper img")
            image_url = img_tag.get("src") if img_tag else None
            image_filename = ""

            if image_url:
                image_filename = os.path.join(IMAGE_FOLDER, os.path.basename(image_url.split("?")[0]))
                with open(image_filename, 'wb') as f:
                    img_data = requests.get(image_url).content
                    f.write(img_data)

            return {
                "Product Name": title,
                "Description": desc_text,
                "Price": price,
                "Image File": image_filename,
                "Product URL": url
            }

        # Run scraper
        product_links = get_product_links(category_url)
        for i, link in enumerate(product_links, 1):
            st.text(f"Scraping product {i}/{len(product_links)}")
            try:
                data = scrape_product_page(link)
                all_products.append(data)
            except Exception as e:
                st.error(f"Failed to scrape: {link} - {e}")
            sleep(0.5)

        # Save Data
        df = pd.DataFrame(all_products)
        data_file = "osc_seeds_data.xlsx"
        df.to_excel(data_file, index=False)

        st.success("✅ Scraping complete!")
        st.markdown("### Download Excel File:")
        with open(data_file, "rb") as f:
            st.download_button("📥 Download .xlsx", f, file_name="osc_seeds_data.xlsx")

        st.markdown("### Download Images:")
        st.write(f"All images are saved in `/{IMAGE_FOLDER}/` folder.")

