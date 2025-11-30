#!/usr/bin/env python
# coding: utf-8

# In[4]:


#pip install selenium beautifulsoup4 webdriver_manager

from bs4 import BeautifulSoup as bs
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

options = webdriver.ChromeOptions()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

# This initializes the driver using 'Service' and 'options' keyword arguments
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# This is the URL for the 'new cars' webpage. 
url = 'https://www.toyotaofdowntownla.com/inventory/new'
driver.get(url)

# Uses Selenium's WebDriverWait to wait 20 seconds fot car inventory content to load
try:
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CLASS_NAME, "srp-vehicle-list-item"))
    )
    print("Page finished rendering. Content loaded.")
except Exception as e:
    print(f"Timed out waiting for page to load: {e}")

# Pulls the HTML code for the specific car
page_source = driver.page_source

# Closes the browser instance used to pull HTML data
driver.quit()

# Creates a BeautifulSoup object from the HTML code pulled
soup = bs(page_source, 'html.parser')

# Selects div tags with all car attributes from car listings
results = soup.select('div.row.mb-5.mt-2')

import json
import pandas as pd

# Populates 'car_list' with all the car attribute data for our first dataframe
car_list = []
for result in results:
    scripts = result.find_all('script', type='application/ld+json')
    for script in scripts:
        json_text = script.string
        if json_text:
            car_data = json.loads(json_text)
            car_list.append({
                'Model': car_data.get('model'),
                'Brand': car_data.get('brand'),
                'Year': car_data.get('vehicleModelDate'),
                'Interior Color': car_data.get('vehicleInteriorColor'),
                'Transmission': car_data.get('vehicleTransmission'),
                'Color': car_data.get('color'),
                'Price': car_data.get('offers', {}).get('price')
            })
car_list
df2 = pd.DataFrame(car_list)

import json

# Populates 'car_url_list' with all the URLs of each new car in Toyota's inventory
car_url_list = []
for result in results:
    scripts = result.find_all('script', type='application/ld+json')
    for script in scripts:
        json_text = script.string
        if json_text:
            car_data = json.loads(json_text)
            car_url_list.append(car_data.get('offers', {}).get('url'))

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time

options = webdriver.ChromeOptions()
options.add_argument("--headless")

# Launches another Chrome browser to extract data from each individual car's webpage
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Populates 'result_list' with the HTML code for each car's webpage
result_list = []
for url in car_url_list:
    url = str(url).strip()
    if not url.startswith("http"):
        continue
    driver.get(url)
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "srp-vehicle-list-item"))
        )
    except Exception as e:
        print(f"Timed out for {url}: {e}")

    # Remove the explicit sleep, if not needed:
    #time.sleep(3)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    results = soup.select("div.details-value")
    result_list.extend(results)
driver.quit()

# Populates 'car' with lists of attributes for each car
cars = []
current_car = []
EXPECTED_FIELDS_PER_CAR = 7
for tag in result_list:
    is_start = False
    span = tag.find("span")
    # Original method
    if span and "ddoa-interior-color" in (span.get("type") or ""):
        is_start = True
    # Fallback: if a new car starts without interior color (e.g., first field is body type)
    elif (
        current_car and len(current_car) >= EXPECTED_FIELDS_PER_CAR and 
        ('Car' in tag.text or 'Utility' in tag.text or 'Mini-van' in tag.text or 'CrewMax' in tag.text)
    ):
        is_start = True
    if is_start:
        if current_car:
            cars.append(current_car)
        current_car = []
    current_car.append(tag)
if current_car:
    cars.append(current_car)

# Cleans the 'cars' list to get rid of extra attrubutes and label missing attributes as 'NA'
for i in range(0, len(cars)):
    car = cars[i]
    if len(car) < 7:
        new_car = car[0:len(car)]
        for j in range(0, 7-len(car)):
            new_car.append('NA')
        cars[i] = new_car
    elif len(car) > 7:
        new_car = car[0:7]
        cars[i] = new_car

import pandas as pd

# Defines a function to create a dictionary from each car containing their individual car attributes
def parse_car_details(car_tags):
    import re
    car_dict = {
        'Interior Color': 'NA',
        'Body Type': 'NA',
        'Drive Type': 'NA',
        'MPG': 'NA',
        'Engine': 'NA',
        'Transmission': 'NA',
        'Model Code': 'NA'
    }

    for tag in car_tags:

        if hasattr(tag, "get_text"):
            text = tag.get_text(strip=True)
        else:
            text = str(tag).strip()
        span = None
        if hasattr(tag, "find") and hasattr(tag, "get"):
            span = tag.find("span")
            if span and hasattr(span, "get"):
                if "ddoa-interior-color" in (span.get("type") or ""):
                    car_dict['Interior Color'] = text
                    continue
        if any(keyword in text for keyword in ['Car', 'Utility', 'Mini-van', 'XtraCab', 'CrewMax', 'Double Cab']):
            if car_dict['Body Type'] == 'NA':
                car_dict['Body Type'] = text
                continue
        if any(keyword in text for keyword in ['Wheel Drive', 'All Wheel', 'Four Wheel', 'Front Wheel', 'Rear Wheel']):
            car_dict['Drive Type'] = text
            continue
        if '/' in text and 'EPA' in text.upper():
            car_dict['MPG'] = text
            continue
        if any(keyword in text for keyword in ['Engine', 'Motor', 'Hybrid', 'Turbo', 'Cyl']) and 'Transmission' not in text:
            car_dict['Engine'] = text
            continue
        if 'Transmission' in text:
            car_dict['Transmission'] = text
            continue
        if isinstance(text, str) and text.isdigit():
            car_dict['Model Code'] = text
            continue
    return car_dict

# Applies the 'parse_car_details' function to all the cars in the new car inventory to populate 'car_table' with dictionaries for each car
car_table = []
for car in cars:
    car_dict = parse_car_details(car)
    car_table.append(car_dict)

# Creates a Pandas dataframe from 'car_table'
df1 = pd.DataFrame(car_table)

# Combines df1 and df2 to create a Pandas dataframe with all the desired information
result_df = pd.concat([df2, df1], axis=1)
result_df


# In[5]:


new_order = ['Model', 'Brand', 'Year', 'Transmission', 'Price', 'Body Type', 'MPG', 'Engine']
toyota_df = result_df[new_order]
toyota_df


# In[6]:


toyota_df.to_csv('Toyota.csv', index=False)

