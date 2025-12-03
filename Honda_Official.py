#!/usr/bin/env python
# coding: utf-8

# In[2]:


#pip install webdriver-manager


# In[3]:


import time
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),
                          options=chrome_options)

driver.get("https://www.hondaoflosangeles.com/searchnew.aspx")

SCROLL_PAUSE = 1.0
max_iterations = 230

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

print(f"Found {len(links)} links")
for L in links:
    print(L)



# In[4]:


import re


# In[5]:


# Find unique models from the links and make a list of their urls
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


# In[6]:


import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import re
import pandas as pd

def setup_driver():
    """Setup undetected Chrome driver."""
    options = uc.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    driver = uc.Chrome(options=options, version_main=None)
    return driver

def scrape_car_data(driver, url, debug=False):
    """Scrape car data from a single Honda inventory page."""
    try:
        driver.get(url)
        time.sleep(5)

        # Check for Cloudflare bot detection
        if "cloudflare" in driver.title.lower():
            print(f"  Warning: Cloudflare detected")
            time.sleep(10)
            if "cloudflare" in driver.title.lower():
                return None

        if debug:
            print(f"\nDEBUG: Page title: {driver.title}")
            print(f"DEBUG: URL: {url}")

        car_data = {'url': url}

        # Extract VIN attribute from URL
        url_parts = url.rstrip('/').split('-')
        if url_parts:
            potential_vin = url_parts[-1]
            if len(potential_vin) == 17:
                car_data['VIN'] = potential_vin.upper()

        # Extract Year, Make, Model, Trim from URL
        url_pattern = re.search(r'/new-[^-]+-(\d{4})-([^-]+)-(.+)-([A-Z0-9]{17})$', url)
        if url_pattern:
            car_data['Year'] = url_pattern.group(1)
            car_data['Make'] = url_pattern.group(2).replace('+', ' ')
            model_and_trim = url_pattern.group(3)
            model_and_trim = model_and_trim.replace('+', ' ')
            parts = model_and_trim.split('-')

            if len(parts) >= 2:
                # Trim and model
                car_data['Trim'] = parts[-1].replace('+', ' ')
                car_data['Model'] = '-'.join(parts[:-1]).replace('-', ' ').replace('+', ' ')
            else:
                # Just model
                car_data['Model'] = model_and_trim.replace('-', ' ')

            if debug:
                print(f"DEBUG: URL parsing - Year: {car_data.get('Year')}, Make: {car_data.get('Make')}, Model: {car_data.get('Model')}, Trim: {car_data.get('Trim')}")

        # Wait for page to load
        wait = WebDriverWait(driver, 15)
        try:
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except:
            pass

        # Get page source for data extraction
        page_text = driver.page_source

        # Try to extract model from page title or headers
        if 'Model' not in car_data or not car_data['Model']:
            # Try page title first
            title = driver.title
            if debug:
                print(f"DEBUG: Page title for model extraction: {title}")

            # Use Pattern to extract model
            title_pattern = re.search(r'(\d{4})\s+([A-Za-z]+)\s+([A-Za-z\s\+]+?)(?:\s+(?:LX|EX|Sport|Touring|Elite|TrailSport|RTL|Limited|SE)|\s*-|\s*\|)', title, re.IGNORECASE)
            if title_pattern:
                car_data['Model'] = title_pattern.group(3).strip()
                if debug:
                    print(f"DEBUG: Extracted model from title: {car_data['Model']}")

        # Look for model in page headers
        if 'Model' not in car_data or not car_data['Model']:
            try:
                # Look for h1, h2 headers that might contain vehicle name
                headers = driver.find_elements(By.XPATH, "//h1 | //h2 | //h3")
                for header in headers:
                    header_text = header.text.strip()
                    if debug:
                        print(f"DEBUG: Checking header: {header_text}")

                    # Try to match "YEAR MAKE MODEL" pattern
                    header_pattern = re.search(r'(\d{4})\s+([A-Za-z]+)\s+([A-Za-z\s\+]+?)(?:\s+(?:LX|EX|Sport|Touring|Elite|TrailSport|RTL|Limited|SE)|$)', header_text, re.IGNORECASE)
                    if header_pattern:
                        if 'Year' not in car_data:
                            car_data['Year'] = header_pattern.group(1)
                        if 'Make' not in car_data:
                            car_data['Make'] = header_pattern.group(2)
                        car_data['Model'] = header_pattern.group(3).strip()
                        if debug:
                            print(f"DEBUG: Extracted model from header: {car_data['Model']}")
                        break
            except:
                pass

        # FExtract from JSON-LD or structured data
        if 'Model' not in car_data or not car_data['Model']:
            json_patterns = [
                r'"model"[:\s]+"([^"]+)"',
                r'"name"[:\s]+"[^"]*?(\d{4})[^"]*?Honda[^"]*?([A-Za-z\s]+?)(?:"|\s+(?:LX|EX|Sport))',
                r'<title>.*?(\d{4}).*?Honda.*?([A-Za-z\s]+?)(?:\s+(?:LX|EX|Sport)|</title>)'
            ]
            for pattern in json_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    if match.lastindex >= 2:
                        car_data['Model'] = match.group(2).strip()
                    else:
                        car_data['Model'] = match.group(1).strip()
                    if debug:
                        print(f"DEBUG: Extracted model from JSON/meta: {car_data['Model']}")
                    break

        # Extract Stock Number (multiple patterns)
        stock_patterns = [
            r'Stock\s*#[:\s]*([A-Z0-9]+)',
            r'stock["\s:]+([A-Z0-9]{6,})',
            r'"stockNumber"[:\s]+"([^"]+)"'
        ]
        for pattern in stock_patterns:
            stock_match = re.search(pattern, page_text, re.IGNORECASE)
            if stock_match and 'Stock' not in car_data:
                car_data['Stock'] = stock_match.group(1).strip()
                if debug:
                    print(f"DEBUG: Found Stock: {car_data['Stock']}")
                break

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
                if debug:
                    print(f"DEBUG: Found Body Style: {car_data['Body Style']}")
                break

        # Extract Exterior Color
        ext_patterns = [
            r'EXTERIOR\s+COLOR[:\s]+([^\n<]+)',
            r'Exterior[:\s]+([A-Za-z\s]+?)(?:\n|Interior|<)',
            r'"exteriorColor"[:\s]+"([^"]+)"',
            r'Ext\.[:\s]+([A-Za-z\s]+)'
        ]
        for pattern in ext_patterns:
            ext_match = re.search(pattern, page_text, re.IGNORECASE)
            if ext_match and 'Exterior Color' not in car_data:
                color = ext_match.group(1).strip()
                # Clean up color name
                color = re.sub(r'\\n.*', '', color).strip()
                if color and len(color) < 50 and not any(x in color.lower() for x in ['interior', 'transmission', 'engine']):
                    car_data['Exterior Color'] = color
                    if debug:
                        print(f"DEBUG: Found Exterior Color: {car_data['Exterior Color']}")
                    break

        # Extract Interior Color
        int_patterns = [
            r'INTERIOR\s+COLOR[:\s]+([^\n<]+)',
            r'Interior[:\s]+([A-Za-z\s]+?)(?:\n|Exterior|<)',
            r'"interiorColor"[:\s]+"([^"]+)"',
            r'Int\.[:\s]+([A-Za-z\s]+)'
        ]
        for pattern in int_patterns:
            int_match = re.search(pattern, page_text, re.IGNORECASE)
            if int_match and 'Interior Color' not in car_data:
                color = int_match.group(1).strip()
                # Clean up color name
                color = re.sub(r'\\n.*', '', color).strip()
                if color and len(color) < 50 and not any(x in color.lower() for x in ['exterior', 'transmission', 'engine']):
                    car_data['Interior Color'] = color
                    if debug:
                        print(f"DEBUG: Found Interior Color: {car_data['Interior Color']}")
                    break

        # Extract Engine
        engine_patterns = [
            r'ENGINE[:\s]+([^\n<]+(?:L|liter)[^\n<]*)',
            r'(\d+\.\d+L[^<\n]*?(?:I-?\d+|V-?\d+)[^<\n]*)',
            r'"engine"[:\s]+"([^"]+)"',
            r'Engine[:\s]+([^\n<]+)'
        ]
        for pattern in engine_patterns:
            engine_match = re.search(pattern, page_text, re.IGNORECASE)
            if engine_match and 'Engine' not in car_data:
                engine = engine_match.group(1).strip()
                engine = re.sub(r'\\n.*', '', engine).strip()
                if engine and len(engine) < 100:
                    car_data['Engine'] = engine
                    if debug:
                        print(f"DEBUG: Found Engine: {car_data['Engine']}")
                    break

        # Extract Transmission
        trans_patterns = [
            r'TRANSMISSION[:\s]+([^\n<]+)',
            r'Transmission[:\s]+([^\n<]+)',
            r'"transmission"[:\s]+"([^"]+)"',
            r'(CVT\s*/\s*(?:FWD|RWD|AWD|4WD))',
            r'(\d+-Speed\s+(?:Automatic|Manual)[^\n<]*)',
            r'(CVT[^\n<]*)'
        ]
        for pattern in trans_patterns:
            trans_match = re.search(pattern, page_text, re.IGNORECASE)
            if trans_match and 'Transmission' not in car_data:
                trans = trans_match.group(1).strip()
                trans = re.sub(r'\\n.*', '', trans).strip()
                if trans and len(trans) < 100:
                    car_data['Transmission'] = trans
                    if debug:
                        print(f"DEBUG: Found Transmission: {car_data['Transmission']}")
                    break

        # Extract Drivetrain
        drive_patterns = [
            r'DRIVETRAIN[:\s]+([^\n<]+)',
            r'\b(FWD|RWD|AWD|4WD|Four Wheel Drive|All Wheel Drive|Front Wheel Drive|Rear Wheel Drive)\b',
            r'"drivetrain"[:\s]+"([^"]+)"'
        ]
        for pattern in drive_patterns:
            drive_match = re.search(pattern, page_text, re.IGNORECASE)
            if drive_match and 'Drivetrain' not in car_data:
                car_data['Drivetrain'] = drive_match.group(1).strip()
                if debug:
                    print(f"DEBUG: Found Drivetrain: {car_data['Drivetrain']}")
                break

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
                    if debug:
                        print(f"DEBUG: Found MPG: {car_data['MPG']}")
                    break

        # Extract Price
        price_patterns = [
            r'PRICE[:\s]+\$\s*([\d,]+)',
            r'\$\s*([\d,]+)\s*MSRP',
            r'"price"[:\s]+(\d+)',
            r'>\s*\$\s*([\d,]+)\s*<'
        ]

        # Extract Price
        try:
            price_elements = driver.find_elements(By.XPATH, 
                "//*[contains(@class, 'price') or contains(@class, 'PRICE')] | " +
                "//*[contains(text(), '$')]"
            )
            for elem in price_elements:
                text = elem.text
                price_match = re.search(r'\$\s*([\d,]+)', text)
                if price_match:
                    price_str = price_match.group(1).replace(',', '')
                    try:
                        price = float(price_str)
                        if 10000 <= price <= 200000 and 'Price' not in car_data:
                            car_data['Price'] = price
                            if debug:
                                print(f"DEBUG: Found Price: {car_data['Price']}")
                            break
                    except:
                        pass
        except:
            pass

        # If price not found, try patterns on page text
        if 'Price' not in car_data:
            for pattern in price_patterns:
                price_match = re.search(pattern, page_text, re.IGNORECASE)
                if price_match:
                    price_str = price_match.group(1).replace(',', '')
                    try:
                        price = float(price_str)
                        if 10000 <= price <= 200000:
                            car_data['Price'] = price
                            if debug:
                                print(f"DEBUG: Found Price: {car_data['Price']}")
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
                if debug:
                    print(f"DEBUG: Found Fuel Type: {car_data['Fuel Type']}")
                break

        # If we found "Hybrid" in model name, set fuel type
        if 'Fuel Type' not in car_data and 'Model' in car_data:
            if 'hybrid' in car_data['Model'].lower():
                car_data['Fuel Type'] = 'Hybrid'

        # Extract Model Code
        model_code_patterns = [
            r'Model\s+Code[:\s]+([A-Z0-9]+)',
            r'MODEL\s+CODE[:\s]+([A-Z0-9]+)',
            r'"modelCode"[:\s]+"([^"]+)"'
        ]
        for pattern in model_code_patterns:
            code_match = re.search(pattern, page_text, re.IGNORECASE)
            if code_match and 'Model Code' not in car_data:
                car_data['Model Code'] = code_match.group(1).strip()
                if debug:
                    print(f"DEBUG: Found Model Code: {car_data['Model Code']}")
                break

        return car_data if len(car_data) > 1 else None

    except Exception as e:
        print(f"  Error: {str(e)[:100]}")
        if debug:
            import traceback
            traceback.print_exc()
        return None

def scrape_all_cars(urls, debug_first=False):
    """Scrape all car URLs and return a pandas DataFrame."""
    cars = {}
    driver = setup_driver()

    try:
        for i, url in enumerate(urls, 1):
            print(f"Scraping {i}/{len(urls)}: {url}")

            debug = debug_first and i <= 3

            car_data = scrape_car_data(driver, url, debug=debug)

            if car_data:
                vin = car_data.get('VIN', f'car_{i}')
                cars[vin] = car_data

                # Print summary
                summary_parts = []
                if 'Year' in car_data:
                    summary_parts.append(car_data['Year'])
                if 'Make' in car_data:
                    summary_parts.append(car_data['Make'])
                if 'Model' in car_data:
                    summary_parts.append(car_data['Model'])
                if 'Trim' in car_data:
                    summary_parts.append(f"({car_data['Trim']})")

                summary = ' '.join(summary_parts) if summary_parts else 'Unknown'

                extras = []
                if 'Price' in car_data:
                    extras.append(f"${car_data['Price']:,.0f}")
                if 'MPG' in car_data:
                    extras.append(f"MPG: {car_data['MPG']}")
                if 'Exterior Color' in car_data:
                    extras.append(f"Color: {car_data['Exterior Color']}")

                extra_info = ' | '.join(extras) if extras else ''
                print(f"  ✓ {summary} {f'- {extra_info}' if extra_info else ''}")
            else:
                print(f"  ✗ No data found")

            delay = random.uniform(3, 6)
            time.sleep(delay)

    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user. Saving data collected so far...")
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
        'Year', 'Make', 'Model', 'Trim', 'VIN', 'Stock', 
        'Price', 'MPG', 'Engine', 'Transmission', 'Drivetrain',
        'Body Style', 'Fuel Type', 'Exterior Color', 'Interior Color', 
        'Model Code', 'url'
    ]

    existing_columns = [col for col in desired_columns if col in df.columns]
    other_columns = [col for col in df.columns if col not in desired_columns]
    final_columns = existing_columns + other_columns

    df = df[final_columns]
    df = df.reset_index(drop=True)

    return df

df = scrape_all_cars(unique_model_urls, debug_first=True)
df


# In[11]:


df2 = df
new_order = ['Model', 'Make', 'Year', 'Transmission', 'Price', 'Body Style', 'MPG', 'Fuel Type']
df2 = df2[new_order]
df2 = df2.rename(columns={'Make':'Brand', 'Body Style':'Body Type', 'Fuel Type':'Engine'})

# In[12]:


df2.to_csv('Honda.csv', index=False)

