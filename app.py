import os
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import io

# Configuration
BASE_URL = "https://www.OSCseeds.com"
OUTPUT_FOLDER = "osc_seeds_data"
EXCEL_FILE = "osc_seeds_products.xlsx"
IMAGE_FOLDER = os.path.join(OUTPUT_FOLDER, "images")

def setup_driver():
    """Set up Selenium WebDriver"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')  # Run in background
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    return driver

def create_output_folder():
    """Create output folder structure"""
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    if not os.path.exists(IMAGE_FOLDER):
        os.makedirs(IMAGE_FOLDER)

def scrape_product_page(driver, url):
    """Scrape individual product page"""
    driver.get(url)
    time.sleep(2)  # Allow page to load
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    product_data = {
        'name': '',
        'price': '',
        'sku': '',
        'description': '',
        'specifications': {},
        'image_url': '',
        'product_url': url
    }
    
    try:
        # Extract basic info - adjust selectors based on actual page structure
        product_data['name'] = soup.find('h1', class_='product-title').text.strip()
        product_data['price'] = soup.find('span', class_='price').text.strip()
        product_data['sku'] = soup.find('span', class_='sku').text.strip().replace('SKU:', '').strip()
        product_data['description'] = soup.find('div', class_='product-description').text.strip()
        
        # Extract specifications table
        spec_table = soup.find('table', class_='specifications')
        if spec_table:
            for row in spec_table.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) == 2:
                    key = cols[0].text.strip()
                    value = cols[1].text.strip()
                    product_data['specifications'][key] = value
        
        # Extract main product image
        img_tag = soup.find('img', class_='product-main-image')
        if img_tag and 'src' in img_tag.attrs:
            product_data['image_url'] = img_tag['src']
            if not product_data['image_url'].startswith('http'):
                product_data['image_url'] = BASE_URL + product_data['image_url']
    
    except Exception as e:
        print(f"Error scraping product page {url}: {str(e)}")
    
    return product_data

def download_image(url, product_id):
    """Download and save product image"""
    if not url:
        return None
    
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            image = Image.open(io.BytesIO(response.content))
            image_path = os.path.join(IMAGE_FOLDER, f"{product_id}.jpg")
            image.save(image_path)
            return image_path
    except Exception as e:
        print(f"Error downloading image {url}: {str(e)}")
    return None

def scrape_category_page(driver, url):
    """Scrape a category page to get product links"""
    driver.get(url)
    time.sleep(2)
    
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    product_links = []
    
    product_items = soup.find_all('div', class_='product-item')
    for item in product_items:
        link = item.find('a', class_='product-link')
        if link and 'href' in link.attrs:
            product_url = link['href']
            if not product_url.startswith('http'):
                product_url = BASE_URL + product_url
            product_links.append(product_url)
    
    return product_links

def main():
    print("Starting OSC Seeds data scraping...")
    start_time = time.time()
    
    # Setup environment
    create_output_folder()
    driver = setup_driver()
    
    try:
        # Get all product URLs (you may need to modify this based on site structure)
        print("Discovering product pages...")
        category_urls = [
            f"{BASE_URL}/vegetables",
            f"{BASE_URL}/flowers",
            f"{BASE_URL}/herbs"
            # Add more categories as needed
        ]
        
        all_product_urls = []
        for category_url in category_urls:
            try:
                product_urls = scrape_category_page(driver, category_url)
                all_product_urls.extend(product_urls)
                print(f"Found {len(product_urls)} products in {category_url}")
            except Exception as e:
                print(f"Error scraping category {category_url}: {str(e)}")
        
        # Scrape each product
        print(f"Found {len(all_product_urls)} products total. Starting scraping...")
        all_products = []
        
        for i, product_url in enumerate(all_product_urls, 1):
            try:
                print(f"Scraping product {i}/{len(all_product_urls)}: {product_url}")
                product_data = scrape_product_page(driver, product_url)
                
                # Download image
                if product_data['image_url']:
                    image_path = download_image(product_data['image_url'], product_data['sku'] or f"product_{i}")
                    product_data['image_path'] = image_path
                
                all_products.append(product_data)
                
            except Exception as e:
                print(f"Error processing product {product_url}: {str(e)}")
        
        # Save to Excel
        print("Saving data to Excel...")
        df = pd.DataFrame(all_products)
        
        # Flatten specifications dictionary into columns
        spec_dfs = []
        for specs in df['specifications']:
            spec_dfs.append(pd.DataFrame([specs]))
        
        if spec_dfs:
            specs_df = pd.concat(spec_dfs, axis=0)
            specs_df.reset_index(drop=True, inplace=True)
            df = pd.concat([df.drop(['specifications'], axis=1), specs_df], axis=1)
        
        df.to_excel(os.path.join(OUTPUT_FOLDER, EXCEL_FILE), index=False)
        
        print(f"Scraping completed successfully in {(time.time() - start_time)/60:.2f} minutes")
        print(f"Data saved to: {os.path.join(OUTPUT_FOLDER, EXCEL_FILE)}")
        print(f"Images saved to: {IMAGE_FOLDER}")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
