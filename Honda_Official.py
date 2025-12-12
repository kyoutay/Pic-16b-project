import time
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
import pandas as pd

chrome_options = Options()
chrome_options.add_argument("--headless=new") # runs Chrome w/o opening any visible windows
chrome_options.add_argument("--disable-gpu") # disables GPU accelerations to avoid rendering issues
chrome_options.add_argument("--window-size=1920,1080") # sets window size to enable scrolling mechanism

# This initializes the driver using 'Service' and 'options' keyword arguments
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# This is the URL for the 'new cars' webpage. 
driver.get("https://www.hondaoflosangeles.com/searchnew.aspx")

def get_car_links(driver):
    """Creates a Chrome browser to scroll through Honda's new car inventory and collect links to each new car's webpage.
    
    Args: 
        driver: An initialized webdriver instance loaded to Honda's new car inventory page
    
    Returns: 
        list: contains urls, each corresponding to a new car listed on Honda's new car inventory page
    """
    SCROLL_PAUSE = 1.0 # amount of time we wait for items to load
    max_iterations = 230 # safety measure so the web scraper doesn't go on forever
    
    prev_count = 0
    same_count_iterations = 0
    
    for i in range(max_iterations):
        # Scroll down the page
        driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(SCROLL_PAUSE)
    
        # Find current number of items
        elems = driver.find_elements(By.CSS_SELECTOR, "a.vehicle-title")
        curr_count = len(elems)
    
        if curr_count > prev_count:
            prev_count = curr_count
            same_count_iterations = 0
        else:
            same_count_iterations += 1
    
        # Stop running once no new items are found
        if same_count_iterations >= 5:
            break
    
    # Parse through html code for links
    soup = BeautifulSoup(driver.page_source, "html.parser")
    links = []
    for a in soup.find_all("a", class_="vehicle-title"):
        if a.has_attr("href"):
            links.append(urljoin(driver.current_url, a["href"]))
    
    driver.quit()
    return links

# Find unique models from the links and make a list of their urls
def find_unique_models(links):
    """Filters through a list of car links and creates a new list containing the links for unique car models. This is to avoid redundancies. 
    
    Args: 
        links (list): a list of car links
    
    Returns:
        list: contains urls for unique car models
    """
    first_instance = {}
    for url in links:
        match = re.search(r'\d{4}-Honda-([^-]+-[^-]+|[^-]+)', url)
        if match:
            model_key = match.group(1)
        else:
            model_key = url  # fallback if no match
        if model_key not in first_instance:
            first_instance[model_key] = url
    unique_model_urls = list(first_instance.values())
    return unique_model_urls

def scrape_car_data(driver, url):
    """Scrapes car attribute data from a single webpage. This webpage specifically contains information about a particular new Honda vehicle.
    
    Args:
        driver: An initialized webdriver instance 
        url (string): A link to a single new Honda vehicle's webpage
        
    Returns:
        dict: contains all found car attribute data for this particular new Honda vehicle"""
    try:
        driver.get(url)
        time.sleep(5)

        # Check for Cloudflare bot detection
        if "cloudflare" in driver.title.lower():
            time.sleep(10)
            if "cloudflare" in driver.title.lower():
                return None

        car_data = {'url': url}

        # Extract Year, Make, Model, Trim from specified URL
        url_pattern = re.search(r'/new-[^-]+-(\d{4})-([^-]+)-(.+)-([A-Z0-9]{17})$', url)
        if url_pattern:
            car_data['Year'] = url_pattern.group(1)
            car_data['Make'] = url_pattern.group(2).replace('+', ' ')
            model_and_trim = url_pattern.group(3)
            model_and_trim = model_and_trim.replace('+', ' ')
            parts = model_and_trim.split('-')

            if len(parts) >= 2:
                # The last part of `parts` is the trim
                car_data['Trim'] = parts[-1].replace('+', ' ')
                car_data['Model'] = '-'.join(parts[:-1]).replace('-', ' ').replace('+', ' ')
            else:
                # The entirety of `parts` is the model
                car_data['Model'] = model_and_trim.replace('-', ' ')

        # Wait for page to load
        wait = WebDriverWait(driver, 15)
        try:
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except:
            pass

        # Get HTML source code and store it in `page_text`
        page_text = driver.page_source

        # Extract Body Style
        body_patterns = [
            r'BODY\s+STYLE[:\s]+([^\n<]+)',
            r'Body\s+Style[:\s]+([^\n<]+)',
            r'"bodyStyle"[:\s]+"([^"]+)"',
            r'(4D\s+(?:Sedan|SUV|Sport Utility|Hatchback|Coupe))',
            r'(\d+D\s+[A-Za-z\s]+)'
        ]
        for pattern in body_patterns:
            body_match = re.search(pattern, page_text, re.IGNORECASE)
            if body_match and 'Body Style' not in car_data:
                car_data['Body Style'] = body_match.group(1).strip()
                break

        # We don't need to extract Transmission anymore since we don't use this in our recommendation program
        car_data['Transmission'] = 'N/A'

        # Extract MPG
        mpg_patterns = [
            r'(\d+)\s+City\s*/\s*(\d+)\s+Highway',
            r'(\d+)\s+city\s*/\s*(\d+)\s+highway',
            r'City/Highway[:\s]+(\d+)\s*/\s*(\d+)',
            r'MPG[:\s]+(\d+)\s*/\s*(\d+)',
            r'(\d+)\s*/\s*(\d+)\s+MPG',
            r'"cityMPG"[:\s]+(\d+).*?"highwayMPG"[:\s]+(\d+)',
            r'"mpgCity"[:\s]+(\d+).*?"mpgHighway"[:\s]+(\d+)'
        ]
        for pattern in mpg_patterns:
            mpg_match = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
            if mpg_match:
                city = int(mpg_match.group(1))
                highway = int(mpg_match.group(2))
                if 10 <= city <= 150 and 10 <= highway <= 150:
                    car_data['MPG'] = f"{city} / {highway}"
                    break

        # Extract Price
        price_patterns = [
            r'PRICE[:\s]+\$\s*([\d,]+)',
            r'\$\s*([\d,]+)\s*MSRP',
            r'"price"[:\s]+(\d+)',
            r'>\s*\$\s*([\d,]+)\s*<'
        ]
        for pattern in price_patterns:
            price_match = re.search(pattern, page_text, re.IGNORECASE)
            if price_match:
                price_str = price_match.group(1).replace(',', '')
                try:
                    price = float(price_str)
                    if 10000 <= price <= 200000:
                        car_data['Price'] = price
                        break
                except:
                    pass

        # Extract Fuel Type
        fuel_patterns = [
            r'FUEL\s+TYPE[:\s]+([^\n<]+)',
            r'Fuel\s+Type[:\s]+([^\n<]+)',
            r'"fuelType"[:\s]+"([^"]+)"',
            r'\b(Gasoline|Diesel|Hybrid|Electric|Plug-in Hybrid|PHEV)\b'
        ]
        for pattern in fuel_patterns:
            fuel_match = re.search(pattern, page_text, re.IGNORECASE)
            if fuel_match and 'Fuel Type' not in car_data:
                car_data['Fuel Type'] = fuel_match.group(1).strip()
                break
        if 'Fuel Type' not in car_data and 'Model' in car_data:
            if 'hybrid' in car_data['Model'].lower():
                car_data['Fuel Type'] = 'Hybrid'
            
        return car_data if len(car_data) > 1 else None

    # Prevent web scraper from crashing due to an error by catching errors
    except Exception as e:
        print(f"  Error: {str(e)[:100]}")
        return None

def scrape_all_cars(urls, debug_first=False):
    """Visits the webpage for each unique new Honda vehicle, extracts data, and puts all the information into a dataframe.
    
    Args:
        urls (list): A list of unique urls to extract data from.
        
    Returns:
        DataFrame: contains car attribute data for each new Honda vehicle."""
        
    cars = {} # a dictionary of cars and their attributes
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        for i, url in enumerate(urls, 1):
            print(f"Scraping {i}/{len(urls)}: {url}")
            car_data = scrape_car_data(driver, url)

            if car_data:
                cars[i] = car_data

            delay = random.uniform(3, 6)
            time.sleep(delay)

    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
    except Exception as e:
        print(f"\n\nUnexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()

    # Convert to DataFrame
    df = pd.DataFrame.from_dict(cars, orient='index')

    # Reorder columns
    desired_columns = [
        'Year', 'Make', 'Model', 'Trim',
        'Price', 'MPG', 'Transmission',
        'Body Style', 'Fuel Type', 
        'url'
    ]

    existing_columns = [col for col in desired_columns if col in df.columns]
    other_columns = [col for col in df.columns if col not in desired_columns]
    final_columns = existing_columns + other_columns

    df = df[final_columns]
    df = df.reset_index(drop=True)

    return df

links = get_car_links(driver)
unique_model_urls = find_unique_models(links)
df = scrape_all_cars(unique_model_urls)

# Additional cleaning with the car DataFrame
new_order = ['Model', 'Make', 'Year', 'Transmission', 'Price', 'Body Style', 'MPG', 'Fuel Type']
df = df[new_order]
df = df.rename(columns={'Make':'Brand', 'Body Style':'Body Type', 'Fuel Type':'Engine'})


df.to_csv('Honda.csv', index=False)

