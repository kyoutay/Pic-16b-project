import pandas as pd
import numpy as np
import xgboost as xgb
import os


class InsurancePricingModel:
    def __init__(self):
        self.freq_model = None
        self.sev_model = None
        self.features = ['VehPower', 'VehAge', 'Density', 'DrivAge']
        self.is_trained = False

    def _preprocess_training_data(self, freq_path, sev_path):
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        df_freq = pd.read_csv(freq_path)
        df_sev = pd.read_csv(sev_path)

        # cleaning frequency data so claims from ids match with ids from severities
        sev_ids = set(df_sev['IDpol'])
        mask = (df_freq['ClaimNb'] >= 1) & (~df_freq['IDpol'].isin(sev_ids))
        df_freq.loc[mask, 'ClaimNb'] = 0

        # prepare frequency dataset to model claims with xgboost
        # We model log(Claims) = log(Exposure) + Model_Output
        df_freq['log_exposure'] = np.log(df_freq['Exposure'])

        # aggregate claim amounts by ID on severity data
        sev_grouped = df_sev.groupby('IDpol')['ClaimAmount'].sum().reset_index()
        
        # merge frequency data onto severity data
        df_merged = pd.merge(df_freq, sev_grouped, on='IDpol', how='left')
        df_merged['ClaimAmount'] = df_merged['ClaimAmount'].fillna(0)
        
        # filter only positive claims for severity model
        df_severity = df_merged[df_merged['ClaimAmount'] > 0].copy()
        
        # average claim amount (the target)
        df_severity['AvgClaimAmount'] = df_severity['ClaimAmount'] / df_severity['ClaimNb']

        return df_freq, df_severity

    def train(self, freq_path="freMTPL2freq.csv", sev_path="freMTPL2sev.csv"):
        """
       trains frequency model and severity model
        """
        df_freq, df_sev = self._preprocess_training_data(freq_path, sev_path)

        # frequency model training
        X_freq = df_freq[self.features]
        y_freq = df_freq['ClaimNb']
        log_exposure = df_freq['log_exposure']

        self.freq_model = xgb.XGBRegressor(
            objective='count:poisson',
            n_estimators=100,
            learning_rate=0.1,
            max_depth=4,
            n_jobs=-1,
            random_state=42
        )
        self.freq_model.fit(X_freq, y_freq, base_margin=log_exposure)

        # severity model training
        X_sev = df_sev[self.features]
        y_sev = df_sev['AvgClaimAmount']
        weights = df_sev['ClaimNb'] 

        self.sev_model = xgb.XGBRegressor(
            objective='reg:gamma',
            n_estimators=100,
            learning_rate=0.05,
            max_depth=3,
            base_score=y_sev.mean(),
            n_jobs=-1,
            random_state=42
        )
        self.sev_model.fit(X_sev, y_sev, sample_weight=weights)
        
        self.is_trained = True

    def get_pure_premium(self, user_data: dict):
        """
        Calculates Pure Premium for a single user.
        
        Args:
            user_data (dict): Dictionary containing keys:
                              ['VehPower', 'VehAge', 'Density', 'DrivAge']
        
        Returns:
            dict: Contains 'frequency', 'severity', and 'pure_premium'
        """
        if not self.is_trained:
            raise Exception("Model is not trained yet. Call .train() first.")

        input_df = pd.DataFrame([user_data])
        
        input_df = input_df[self.features]

        annual_offset = [0.0] 
        freq_pred = self.freq_model.predict(input_df, base_margin=annual_offset)[0]

        sev_pred = self.sev_model.predict(input_df)[0]

        pure_premium = freq_pred * sev_pred

        return {
            "predicted_frequency": float(freq_pred),
            "predicted_severity": float(sev_pred),
            "pure_premium": float(pure_premium)
        }

if __name__ == "__main__":
    model = InsurancePricingModel()
    
    try:
        model.train("freMTPL2freq.csv", "freMTPL2sev.csv")

        test_driver = {
            'VehPower': 5,
            'VehAge': 1,
            'Density': 3077,
            'DrivAge': 50
        }
        
        result = model.get_pure_premium(test_driver)
        
        print("\n--- Prediction for Test Driver ---")
        print(f"Input: {test_driver}")
        print(f"Predicted Frequency: {result['predicted_frequency']:.4f}")
        print(f"Predicted Severity:  {result['predicted_severity']:.2f}")
        print(f"Pure Premium:        {result['pure_premium']:.2f}")
        
    except FileNotFoundError:
        print("CSVs not found")