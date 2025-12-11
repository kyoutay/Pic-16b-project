from flask import Flask, render_template_string, request, redirect, url_for, jsonify
import pandas as pd
import numpy as np
import os
import sys
from premium_model import InsurancePricingModel
import subprocess
import threading
import plotly.express as px
import plotly.io as pio

app = Flask(__name__)

# Load the cities CSV file
csv_path = os.path.join(os.path.dirname(__file__), 'uscities.csv')
cities_df = pd.read_csv(csv_path)

# Initialize and train the insurance pricing model
pricing_model = InsurancePricingModel()
pricing_model.train("freMTPL2freq.csv", "freMTPL2sev.csv")

def get_city_density(location):
    """Retrieves population density for a given city and state.
    
    Args:
        location (str): City and state in "City, State" format.
    
    Returns:
        float: Population density in people per square kilometer, or None if not found.
    """
    location = location.strip()
    
    # Try exact match first with "City, State" format
    if ',' in location:
        city, state = location.split(',')
        city = city.strip()
        state = state.strip()
        match = cities_df[(cities_df['city_ascii'].str.lower() == city.lower()) & 
                          (cities_df['state_id'].str.lower() == state.lower())]
    else:
        # Try matching just the city name
        match = cities_df[cities_df['city_ascii'].str.lower() == location.lower()]
    
    if not match.empty:
        density = match.iloc[0]['density']
        return float(density)
    return None

scraper_status = {'running': False, 'complete': False}
# Stores the most recently submitted user profile so other routes can access
# the user's driver age and city density when computing premiums. default values to create dictionary that is later updated with 
user_profile = {
  'DrivAge': 30,
  'Density': 1000,
  'Location': None
}

def generate_recs(df, brand_pref, price_pref, price_weight, mpg_pref, mpg_weight, 
                  size_pref, size_weight):
    """Generates top 5 car recommendations based on weighted user preferences.
    
    Calculates a composite score for each vehicle based on user preferences for brand,
    price, MPG, and vehicle size. Weights determine the relative importance of each criterion.
    
    Args:
        df (pd.DataFrame): Car inventory data with columns: Model, Brand, Year, Price,
            CTY MPG, HWAY MPG, Size.
        brand_pref (list): Preferred car brands (e.g., ['Toyota', 'Honda']).
        price_pref (float): Target price point in dollars.
        price_weight (int): Importance weight for price (0-10).
        mpg_pref (float): Target fuel efficiency in miles per gallon.
        mpg_weight (int): Importance weight for MPG (0-10).
        size_pref (float): Target number of seats.
        size_weight (int): Importance weight for size (0-10).
    
    Returns:
        pd.DataFrame: Top 5 recommended vehicles with columns: Model, Brand, Year,
            Price, CTY MPG, HWAY MPG, Size. Returns empty DataFrame if no matches found.
    """

    df = df.copy()

    # Calculates average MPG
    df['Avg MPG'] = df[['CTY MPG', 'HWAY MPG']].mean(axis=1)

    # Consider brand preferences
    if brand_pref:
        df = df[df['Brand'].isin(brand_pref)]

    if df.empty:
        return pd.DataFrame()

    # Creates score column to determine 'TOP 5' recommendations
    df['Score'] = 0.0

    # Calculates Price Score
    if price_weight > 0:
        price_diff = abs(df['Price'] - price_pref)
        max_diff = price_diff.max()
        if max_diff > 0:
            price_score = 1 - (price_diff / max_diff)
            df['Score'] += price_score * price_weight

    # Calculates MPG Score
    if mpg_weight > 0:
        mpg_diff = abs(df['Avg MPG'] - mpg_pref)
        max_diff = mpg_diff.max()
        if max_diff > 0:
            mpg_score = 1 - (mpg_diff / max_diff)
            df['Score'] += mpg_score * mpg_weight

    # Calculates Size Score
    if size_weight > 0:
        size_diff = abs(df['Size'] - size_pref)
        max_diff = size_diff.max()
        if max_diff > 0:
            size_score = 1 - (size_diff / max_diff)
            df['Score'] += size_score * size_weight
        else:
            # All sizes are the same
            df['Score'] += size_weight

    # Sorts cars by score and gets TOP 5
    top_5 = df.nlargest(5, 'Score')[['Model', 'Brand', 'Year', 'Price', 
                                       'CTY MPG', 'HWAY MPG', 'Size']]

    return top_5.reset_index(drop=True)

def run_scraper(script_name):
    """Executes a web scraper script and handles errors appropriately.
    
    Args:
        script_name (str): Name of the Python scraper script to execute.
    
    Raises:
        subprocess.CalledProcessError: If the scraper script exits with non-zero code.
        Exception: For other unexpected errors during execution.
    """
    print(f"\nStarting {script_name}")
    try:
        subprocess.run(
            [sys.executable, script_name],
            check=True 
        )
        print(f"Successfully finished {script_name}")
    except Exception as e:
        print(f"Error while running.")
        raise

def run_scrapers_background():
    """Executes all web scrapers sequentially in background thread.
    
    Runs Honda, Toyota, and recommendation generator scrapers in order.
    Updates the global scraper_status dictionary to track progress.
    """
    global scraper_status
    scraper_status['running'] = True
    scraper_status['complete'] = False
    
    run_scraper('Honda_Official.py')
    run_scraper('Toyota_Official.py')
    run_scraper('Rec_Generator.py')
    
    scraper_status['running'] = False
    scraper_status['complete'] = True
    
def generate_report(recommendations, user_profile=None):
    """Generates a comprehensive PDF report with vehicle recommendations and analytics.
    
    Creates visualizations for price, MPG, and insurance premiums, then compiles
    a LaTeX document with recommendations and premium estimates based on the user's
    profile (age and location density).
    
    Args:
        recommendations (pd.DataFrame): DataFrame containing recommended vehicles with
            columns: Model, Brand, Year, Price, CTY MPG, HWAY MPG, Size.
        user_profile (dict, optional): User profile with keys 'DrivAge' and 'Density'.
            If not provided, uses the global user_profile dictionary. Defaults to None.
    
    Note:
        Generates output files:
        - figures/wheel_png_1.png through wheel_png_4.png (visualizations)
        - recommendations.tex (list of recommended cars)
        - rec_summary.tex (summary of recommendations)
        - premium.tex (insurance premiums)
        - Report_Template.pdf (final compiled report)
    """

    # Compute premiums first before creating visualizations
    print("Computing premiums for recommended vehicles...")
    # If no profile supplied, fall back to the module-level user_profile
    if user_profile is None:
      user_profile = globals().get('user_profile', {'DrivAge': 30, 'Density': 1000})
    
    premiums = []
    for index, car in recommendations.iterrows():
      # Prefer Avg MPG if available, otherwise average CTY/HWAY MPG
      if 'Avg MPG' in recommendations.columns:
        mpg = float(car.get('Avg MPG', np.nan))
      else:
        cty = float(car.get('CTY MPG', np.nan)) if not pd.isna(car.get('CTY MPG', np.nan)) else 0.0
        hwy = float(car.get('HWAY MPG', np.nan)) if not pd.isna(car.get('HWAY MPG', np.nan)) else 0.0
        mpg = (cty + hwy) / 2.0 if (cty or hwy) else 0.0

      vehpower = 13975 * np.exp(-0.27 * mpg) + 4 #mpg to vehpower conversion model found as per mpg_to_VehPower_model.ipynb

      user_data = {
        'VehPower': float(vehpower),
        'VehAge': 1,
        'Density': float(user_profile.get('Density', 1000)), # gets from user profile, otherwise defaults to 1000 if unvailable
        'DrivAge': int(user_profile.get('DrivAge', 30)) # gets from user profile, otherwise defaults to 30 if unavailable
      }

      try:
        pred = pricing_model.get_pure_premium(user_data)
        gross = float(pred.get('gross_prem', np.nan))
      except Exception as e:
        print(f"Error computing premium for {car.get('Model', 'Unknown')}: {e}")
        gross = float('nan')

      print(f"{int(car.get('Year',0))} {car.get('Brand','')} {car.get('Model','')}: MPG={mpg:.2f} VehPower={vehpower:.2f} GrossPrem={gross:.2f}")
      premiums.append(gross)

    # Attach premiums to recommendations DataFrame
    recommendations = recommendations.copy()
    recommendations['GrossPremium'] = premiums
    
    # Create a unique label for each car sso plotly doesn't combine
    recommendations['CarLabel'] = (recommendations.index.astype(str) + ': ' +
                                     recommendations['Year'].astype(int).astype(str) + ' ' + 
                                     recommendations['Brand'] + ' ' + 
                                     recommendations['Model'])
    
    # Creates Visualizations
    print("Generating visualizations...")
    os.makedirs('figures', exist_ok=True)
    
    fig1 = px.bar(recommendations, x='CarLabel', y='Price', height=400)
    fig1.write_image("figures/wheel_png_1.png", scale=2)
    
    fig2 = px.bar(recommendations, x='CarLabel', y='CTY MPG', height=400)
    fig2.write_image("figures/wheel_png_2.png", scale=2)
    
    fig3 = px.bar(recommendations, x='CarLabel', y='HWAY MPG', height=400)
    fig3.write_image("figures/wheel_png_3.png", scale=2)
    
    fig4 = px.bar(recommendations, x='CarLabel', y='GrossPremium', height=400)
    fig4.write_image("figures/wheel_png_4.png", scale=2)
    
    print("Visualizations complete")
    
    # Creates Recommendation Text File
    print("Generating recommendations.tex...")
    latex_list = ""
    for index, car in recommendations.iterrows():
        car_name = f"{int(car['Year'])} {car['Brand']} {car['Model']}" 
        latex_list += f"\\item {car_name}.\n"
    
    with open("recommendations.tex", "w") as f:
        f.write(latex_list)
    print("recommendations.tex generated!")
    
    # Creates Recommendation Summary Text File
    print("Generating rec_summary.text...")
    latex_recs =""
    i = 0
    for index, car in recommendations.iterrows():
        car_name = f"{int(car['Year'])} {car['Brand']} {car['Model']}"
        i = i + 1
        if i == 5:
            latex_recs += f"and {car_name}"
        else:
            latex_recs += f"{car_name}, "
    with open("rec_summary.tex", "w") as f:
         f.write(latex_recs)
    print("rec_summary.tex generated!")  
    
    print("Generating premium.tex...")
    prem_list = ""
    for index, car in recommendations.iterrows():
        car_name = f"{int(car['Year'])} {car['Brand']} {car['Model']}" 
        prem = car.get('GrossPremium', float('nan'))
        prem_list += f"\\item {car_name}: \\$ {prem:.2f}\n"

    with open("premium.tex", "w") as f:
        f.write(prem_list)
    print("premium.tex generated!")

    # Compiles PDF 
    print("\nCompiling LaTeX to PDF...")
    try:
        result = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', 'Report_Template.tex'], 
            capture_output=True,
            text=True,
            check=True
        )
        print("PDF generated: Report_Template.pdf")
    except subprocess.CalledProcessError as e:
        print("Compilation failed.")

HOME_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Home</title>
    <style>
      body { font-family: 'Segoe UI', Arial, sans-serif; background: #f4f7fa; margin: 0; }
      .container { background: #fff; max-width: 480px; margin: 4em auto; padding: 2.5em; border-radius: 16px;
                   box-shadow: 0 4px 32px rgba(0, 0, 0, 0.08); text-align: center; }
      h1 { color: #00669b; margin-bottom: 1.1em; }
      .profile-btn { background: #00669b; color: #fff; border: none; border-radius: 6px; font-size: 1.09em; 
                     padding: 0.8em 1.8em; cursor: pointer; margin-top: 15px;
                     box-shadow: 0 2px 4px rgba(140,180,214,0.05); transition: background 0.2s; }
      .profile-btn:hover { background: #0098db; }
      .scraper-btn { background: #28a745; color: #fff; border: none; border-radius: 6px; font-size: 1.09em; 
                     padding: 0.8em 1.8em; cursor: pointer; margin-top: 15px;
                     box-shadow: 0 2px 4px rgba(140,180,214,0.05); transition: background 0.2s; }
      .scraper-btn:hover { background: #218838; }
      .scraper-btn:disabled { background: #6c757d; cursor: not-allowed; }
      .button-group { display: flex; flex-direction: column; gap: 10px; align-items: center; }
      .status-message { margin-top: 15px; padding: 10px; border-radius: 6px; font-size: 0.95em; }
      .status-success { background: #d4edda; color: #155724; }
      .status-running { background: #fff3cd; color: #856404; }
      
      /* Loading spinner */
      .spinner {
        border: 3px solid #f3f3f3;
        border-top: 3px solid #28a745;
        border-radius: 50%;
        width: 30px;
        height: 30px;
        animation: spin 1s linear infinite;
        margin: 10px auto;
        display: none;
      }
      
      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }
    </style>
    <script>
      let checkInterval;
      
      function runScrapers() {
        const btn = document.getElementById('scraperBtn');
        const statusDiv = document.getElementById('status');
        const spinner = document.getElementById('spinner');
        
        btn.disabled = true;
        btn.textContent = 'Running Scrapers...';
        statusDiv.className = 'status-message status-running';
        statusDiv.textContent = 'Web scrapers are running. This will take approximately 30 minutes.';
        statusDiv.style.display = 'block';
        spinner.style.display = 'block';
        
        fetch('/run_scrapers', { method: 'POST' })
          .then(response => response.json())
          .then(data => {
            // Start checking status every 2 seconds
            checkInterval = setInterval(checkScraperStatus, 2000);
          })
          .catch(error => {
            btn.disabled = false;
            btn.textContent = 'Run Web Scrapers';
            statusDiv.textContent = 'Error starting scrapers';
            spinner.style.display = 'none';
          });
      }
      
      function checkScraperStatus() {
        fetch('/scraper_status')
          .then(response => response.json())
          .then(data => {
            if (data.complete) {
              clearInterval(checkInterval);
              const btn = document.getElementById('scraperBtn');
              const statusDiv = document.getElementById('status');
              const spinner = document.getElementById('spinner');
              
              btn.disabled = false;
              btn.textContent = 'Run Web Scrapers';
              statusDiv.className = 'status-message status-success';
              statusDiv.textContent = 'Web Scrapers are Complete! Inventory has been updated.';
              spinner.style.display = 'none';
            }
          });
      }
    </script>
</head>
<body>
  <div class="container">
    <h1>Welcome to Wheel Finder!</h1>
    <p>Click below to create your user profile.</p>
    <div class="button-group">
      <form action="{{ url_for('profile') }}">
        <button class="profile-btn" type="submit">Create Profile</button>
      </form>
      <button class="scraper-btn" id="scraperBtn" onclick="runScrapers()">Run Web Scrapers</button>
      <div class="spinner" id="spinner"></div>
      <div id="status" class="status-message" style="display: none;"></div>
    </div>
  </div>
</body>
</html>
'''

PROFILE_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>User Profile</title>
    <style>
      body { font-family: 'Segoe UI', Arial, sans-serif; background: #f4f7fa; margin: 0; }
      .container { background: #fff; max-width: 500px; margin: 3em auto; padding: 2.5em;
                   border-radius: 16px; box-shadow: 0 4px 32px rgba(0, 0, 0, 0.08);}
      h2 { color: #00669b; margin-bottom: 1.1em; }
      .form-row { margin-bottom: 1.1em; }
      label { display: block; margin-bottom: 0.3em; font-weight: 500;}
      input, select {
        width: 100%; font-size: 1.03em; padding: 0.6em 0.5em; margin-top: 0.1em;
        border: 1px solid #a3bcd6; border-radius: 4px; background: #f7fafc;
      }
      button {
        background: #00669b; color: #fff; border: none; border-radius: 6px;
        font-size: 1.07em; padding: 0.8em 2em; cursor: pointer;
        margin-top: 12px; box-shadow: 0 2px 4px rgba(140,180,214,0.08);
        transition: background 0.2s;
      }
      button:hover { background: #0098db; }
      .result { margin-top: 2em; background: #e8f7fd; border-radius: 8px; padding: 1.1em; }
      .next-btn { background: #0098db; color: #fff; border: none; border-radius: 6px; padding: 0.7em 2em;
                 font-size: 1.04em; margin-top: 1em; cursor: pointer;}
      .next-btn:hover { background: #42b1f5; }
    </style>
</head>
<body>
  <div class="container">
    <h2>Create Your Profile</h2>
    <form method="post">
      <div class="form-row">
        <label for="age">Age</label>
        <input id="age" name="age" type="number" min="0" max="120" required>
      </div>
      <div class="form-row">
        <label for="location">Location</label>
        <input id="location" name="location" type="text" placeholder="City, State" required>
      </div>
      <button type="submit">Submit</button>
    </form>
    {% if result %}
      <div class="result">
        <h4>Your Profile:</h4>
        <ul>
          <li>Age: {{ result['age'] }}</li>
          <li>Location: {{ result['location'] }}</li>
          <li>City Density (people/sq km): {{ result['density'] }}</li>
        </ul>
        <form action="{{ url_for('preferences') }}">
          <button class="next-btn" type="submit">Set Preferences</button>
        </form>
      </div>
    {% endif %}
  </div>
</body>
</html>
'''

PREFERENCES_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Preferences</title>
    <style>
      body { font-family: 'Segoe UI', Arial, sans-serif; background: #f4f7fa; margin: 0; }
      .container {
        background: #fff;
        max-width: 800px;
        margin: 3em auto;
        padding: 2em 2.5em 2em 2.5em;
        border-radius: 16px;
        box-shadow: 0 4px 32px rgba(0, 0, 0, 0.08);
      }
      h2 {
        margin-bottom: 1.5em;
        color: #00669b;
        text-align: center;
      }
      .section {
        margin-bottom: 2em;
        padding-bottom: 1.5em;
        border-bottom: 1px solid #e0e0e0;
      }
      .section:last-of-type {
        border-bottom: none;
      }
      .section-title {
        font-weight: 600;
        font-size: 1.1em;
        margin-bottom: 1em;
        color: #00669b;
      }
      .checkbox-row {
        margin-bottom: 0.8em;
      }
      .checkbox-label {
        display: inline-flex;
        align-items: center;
        cursor: pointer;
        font-size: 1.05em;
        user-select: none;
        padding: 0.4em 0;
      }
      .checkbox-label input[type="checkbox"] {
        width: 20px;
        height: 20px;
        margin-right: 10px;
        cursor: pointer;
      }
      .pref-row {
        display: flex;
        align-items: center;
        margin-bottom: 1.2em;
        gap: 1em;
      }
      .pref-label {
        min-width: 120px;
        font-weight: 500;
        font-size: 1.05em;
      }
      .input-group {
        display: flex;
        align-items: center;
        gap: 1em;
        flex: 1;
      }
      .input-wrapper {
        display: flex;
        flex-direction: column;
        gap: 0.3em;
      }
      .input-wrapper label {
        font-size: 0.9em;
        color: #666;
      }
      .input-wrapper input {
        padding: 0.5em;
        border: 1px solid #a3bcd6;
        border-radius: 4px;
        background: #f7fafc;
        font-size: 1em;
        width: 120px;
      }
      .weight-wrapper {
        display: flex;
        flex-direction: column;
        gap: 0.3em;
      }
      .weight-wrapper label {
        font-size: 0.9em;
        color: #666;
      }
      .weight-wrapper select {
        padding: 0.5em;
        border: 1px solid #a3bcd6;
        border-radius: 4px;
        background: #f7fafc;
        font-size: 1em;
        width: 80px;
      }
      button {
        background: #00669b;
        color: #fff;
        padding: 0.7em 2em;
        border: none;
        border-radius: 6px;
        font-size: 1.04em;
        cursor: pointer;
        box-shadow: 0 2px 4px rgba(140,180,214,0.1);
        margin-top: 12px;
        transition: background 0.2s;
      }
      button:hover {
        background: #0098db;
      }
      .recommendations {
        margin-top: 2em;
        background: #e8f7fd;
        border-radius: 8px;
        padding: 1.5em;
      }
      .recommendations h3 {
        color: #00669b;
        margin-top: 0;
        margin-bottom: 1em;
      }
      .car-card {
        background: white;
        border-radius: 8px;
        padding: 1em;
        margin-bottom: 1em;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      }
      .car-card h4 {
        margin: 0 0 0.5em 0;
        color: #00669b;
      }
      .car-details {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 0.5em;
        font-size: 0.95em;
      }
      .car-details span {
        color: #555;
      }
      .no-results {
        text-align: center;
        padding: 2em;
        color: #666;
      }
    </style>
</head>
<body>
    <div class="container">
    <h2>Set Your Preferences</h2>
    <form method="post">
      <div class="section">
        <div class="section-title">Brand Preferences</div>
        <div class="checkbox-row">
          <label class="checkbox-label">
            <input type="checkbox" name="brand_pref" value="Toyota">
            Toyota
          </label>
        </div>
        <div class="checkbox-row">
          <label class="checkbox-label">
            <input type="checkbox" name="brand_pref" value="Honda">
            Honda
          </label>
        </div>
      </div>

      <div class="section">
        <div class="section-title">Vehicle Preferences</div>
        
        <div class="pref-row">
          <div class="pref-label">Price:</div>
          <div class="input-group">
            <div class="input-wrapper">
              <label>Target Price ($)</label>
              <input type="number" name="price_pref" step="0.01" min="0" placeholder="0">
            </div>
            <div class="weight-wrapper">
              <label>Importance (0-10)</label>
              <select name="price_weight">
                <option value="0">0</option>
                <option value="1">1</option>
                <option value="2">2</option>
                <option value="3">3</option>
                <option value="4">4</option>
                <option value="5">5</option>
                <option value="6">6</option>
                <option value="7">7</option>
                <option value="8">8</option>
                <option value="9">9</option>
                <option value="10">10</option>
              </select>
            </div>
          </div>
        </div>

        <div class="pref-row">
          <div class="pref-label">Number of Seats:</div>
          <div class="input-group">
            <div class="input-wrapper">
              <label>Desired Seats</label>
              <input type="number" name="size_pref" step="0.01" min="0" placeholder="0">
            </div>
            <div class="weight-wrapper">
              <label>Importance (0-10)</label>
              <select name="size_weight">
                <option value="0">0</option>
                <option value="1">1</option>
                <option value="2">2</option>
                <option value="3">3</option>
                <option value="4">4</option>
                <option value="5">5</option>
                <option value="6">6</option>
                <option value="7">7</option>
                <option value="8">8</option>
                <option value="9">9</option>
                <option value="10">10</option>
              </select>
            </div>
          </div>
        </div>

        <div class="pref-row">
          <div class="pref-label">MPG:</div>
          <div class="input-group">
            <div class="input-wrapper">
              <label>Target MPG</label>
              <input type="number" name="mpg_pref" step="0.01" min="0" placeholder="0">
            </div>
            <div class="weight-wrapper">
              <label>Importance (0-10)</label>
              <select name="mpg_weight">
                <option value="0">0</option>
                <option value="1">1</option>
                <option value="2">2</option>
                <option value="3">3</option>
                <option value="4">4</option>
                <option value="5">5</option>
                <option value="6">6</option>
                <option value="7">7</option>
                <option value="8">8</option>
                <option value="9">9</option>
                <option value="10">10</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <button type="submit">Get Recommendations</button>
    </form>
    {% if recommendations is not none %}
      <div class="recommendations">
        <h3>Top 5 Recommended Vehicles</h3>
        {% if recommendations|length > 0 %}
          {% for idx, car in recommendations.iterrows() %}
            <div class="car-card">
              <h4>{{ car['Year'] }} {{ car['Brand'] }} {{ car['Model'] }}</h4>
              <div class="car-details">
                <span><strong>Price:</strong> ${{ "%.2f"|format(car['Price']) }}</span>
                <span><strong>Seats:</strong> {{ car['Size']|int }}</span>
                <span><strong>City MPG:</strong> {{ car['CTY MPG']|int }}</span>
                <span><strong>Highway MPG:</strong> {{ car['HWAY MPG']|int }}</span>
              </div>
            </div>
          {% endfor %}
        {% else %}
          <div class="no-results">
            <p>No vehicles match your preferences. Try adjusting your criteria or run the web scrapers to update inventory.</p>
          </div>
        {% endif %}
      </div>
    {% endif %}
    </div>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(HOME_HTML)

@app.route('/run_scrapers', methods=['POST'])
def run_scrapers():
    """API endpoint to trigger web scraper execution.
    
    Initiates web scrapers in a background thread to collect car inventory data
    from Honda and Toyota official sources without blocking the web request.
    
    Returns:
        dict: JSON response with status indicator.
    """
    global scraper_status
    scraper_status['running'] = False
    scraper_status['complete'] = False
    
    # Run scrapers in a background thread so the request returns immediately
    thread = threading.Thread(target=run_scrapers_background)
    thread.daemon = True
    thread.start()
    return jsonify({'status': 'started'})

@app.route('/scraper_status', methods=['GET'])
def check_scraper_status():
    """API endpoint to check web scraper progress.
    
    Returns:
        dict: JSON response with scraper status flags (running, complete).
    """
    global scraper_status
    return jsonify(scraper_status)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    """Handles user profile creation with age and location information.
    
    On GET: Displays profile form.
    On POST: Processes submitted profile data, looks up city density, and stores
        user information in global user_profile dictionary.
    
    Returns:
        str: Rendered HTML template with profile form and results (if submitted).
    """
    global user_profile
    result = None
    if request.method == 'POST':
        location = request.form['location']
        density = get_city_density(location)
        age = int(request.form['age'])
        
        # Store user profile globally so it can be accessed in generate_report
        user_profile['DrivAge'] = age
        user_profile['Density'] = density if density else 1000
        user_profile['Location'] = location
        
        result = {
            'age': request.form['age'],
            'location': location,
            'density': f"{density:.1f}" if density else "Not found",
        }
    return render_template_string(PROFILE_HTML, result=result)

@app.route('/preferences', methods=['GET', 'POST'])
def preferences():
    """Handles vehicle preference selection and generates recommendations.
    
    On GET: Displays preference form for brands, price, MPG, and vehicle size.
    On POST: Processes preferences, generates top 5 recommendations from inventory,
        calculates insurance premiums, and generates a PDF report.
    
    Returns:
        str: Rendered HTML template with preference form and recommendations (if submitted).
    """
    global user_profile
    recommendations = None
    if request.method == 'POST':
        # Brand preferences
        brand_pref = request.form.getlist('brand_pref')
        
        # Price preference
        price_pref = request.form.get('price_pref', '')
        price_pref = float(price_pref) if price_pref else 0.0
        price_weight = int(request.form.get('price_weight', 0))
        
        # Size preference
        size_pref = request.form.get('size_pref', '')
        size_pref = float(size_pref) if size_pref else 0.0
        size_weight = int(request.form.get('size_weight', 0))
        
        # MPG preference
        mpg_pref = request.form.get('mpg_pref', '')
        mpg_pref = float(mpg_pref) if mpg_pref else 0.0
        mpg_weight = int(request.form.get('mpg_weight', 0))
        
        # Debugging Print Statements
        print(f"\n--- User Preferences ---")
        print(f"brand_pref: {brand_pref}")
        print(f"price_pref: {price_pref}, price_weight: {price_weight}")
        print(f"size_pref: {size_pref}, size_weight: {size_weight}")
        print(f"mpg_pref: {mpg_pref}, mpg_weight: {mpg_weight}")
        sys.stdout.flush()
        
        # Loads inventory dataframe and generates recommendations based on user preferences
        try:
            inventory_df = pd.read_csv('Wheelfinder_Inventory.csv')
            recommendations = generate_recs(
                inventory_df,
                brand_pref,
                price_pref,
                price_weight,
                mpg_pref,
                mpg_weight,
                size_pref,
                size_weight
            )
            print(f"\nGenerated Recommendations")
            print(recommendations)
            sys.stdout.flush()
            generate_report(recommendations, user_profile)
            
        except FileNotFoundError:
            print("Wheelfinder_Inventory.csv not found. Please run the web scrapers first.")
            recommendations = pd.DataFrame()
        except Exception as e:
            print(f"Error generating recommendations: {e}")
            recommendations = pd.DataFrame()
        
    return render_template_string(PREFERENCES_HTML, recommendations=recommendations)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, port=8000)
