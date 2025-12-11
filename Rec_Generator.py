import pandas as pd
import numpy as np

Honda = pd.read_csv("Honda.csv")
Toyota = pd.read_csv("Toyota.csv")
combined_df = pd.concat([Honda, Toyota], ignore_index=True)

# Extract the first `## / ##` pattern from each string in MPG column
combined_df['MPG'] = combined_df['MPG'].str.extract(r'(\d+\s*/\s*\d+)', expand=False)

# Change each data entry to be exactly in the form '## / ##'
combined_df['MPG'] = combined_df['MPG'].str.replace(r'\s*/\s*', ' / ', regex=True)

# Split the values in MPG and put them into respective new columns
combined_df[['CTY MPG', 'HWAY MPG']] = combined_df['MPG'].str.split(' / ', expand=True)

# Convert the values of CTY MPG and HWAY MPG to floats
combined_df[['CTY MPG', 'HWAY MPG']] = combined_df[['CTY MPG', 'HWAY MPG']].astype(float)

# Remove the original MPG 
combined_df.drop('MPG', axis=1, inplace=True)
combined_df.drop('Transmission', axis=1, inplace=True)
combined_df.drop('Engine', axis=1, inplace=True)

# Dictionary used to map body type to seats
bodytype_to_seats = {
    "Sedan": 5,
    "Sport Utility": 5,
    "Passenger Van": 12,
    "Crew Cab": 5,
    "Hatchback": 5,
    "4dr Car": 5,
    "Double Cab": 5,
    "XtraCab": 4,
    "CrewMax": 5,
    "Mini-van, Passenger": 7,
    "2dr Car": 4,
}

# Creates size column with number of seats in vehicle
combined_df["Size"] = combined_df["Body Type"].map(bodytype_to_seats)
combined_df.drop('Body Type', axis=1, inplace=True)
combined_df = combined_df.replace({None: np.nan})
combined_df.to_csv('Wheelfinder_Inventory.csv', index=False, na_rep='NA')

def generate_recs(df, brand_pref, price_pref, price_weight, mpg_pref, mpg_weight, 
                  size_pref, size_weight):
    """
    Generates TOP 5 car recommendations based on user preferences.

    Parameters:
    - df: DataFrame containing car data with columns: Model, Brand, Year, Price, 
          CTY_MPG, HWAY_MPG, Size (this data was collected by web scrapers)
    - brand_pref: list object containing preferred brands
    - price_pref: preferred price point (float)
    - price_weight: importance of price (int from 0-10)
    - mpg_pref: preferred MPG (float)
    - mpg_weight: importance of MPG (int from 0-10)
    - size_pref: preferred size (float)
    - size_weight: importance of size (int from 0-10)

    Returns:
    - DataFrame with top 5 recommended cars and their attributes
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

