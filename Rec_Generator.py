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
