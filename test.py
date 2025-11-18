from premium_model import InsurancePricingModel

pricer = InsurancePricingModel()

pricer.train(freq_path="freMTPL2freq.csv", sev_path="freMTPL2sev.csv")

new_customer = {
    'VehPower': 5,
    'VehAge': 1,
    'Density': 3077,
    'DrivAge': 50
}

results = pricer.get_pure_premium(new_customer)

print(f"The estimated premium is: ${results['pure_premium']:.2f}")