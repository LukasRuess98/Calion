import pandas as pd

df = pd.read_csv('data/Import_Data.csv')
max_dem = df['waermebedarf_MWth'].max()
min_dem = df['waermebedarf_MWth'].min()
mean_dem = df['waermebedarf_MWth'].mean()

print(f"Data: {len(df)} timesteps")
print(f"Max demand:  {max_dem:.2f} MW")
print(f"Min demand:  {min_dem:.2f} MW")
print(f"Mean demand: {mean_dem:.2f} MW")
print(f"\n Stadtbach assets:")
print(f"HKW:    75 MW")
print(f"GTOST:  41 MW")
print(f"BMHKW:  15 MW")
print(f"Total: 131 MW")
print(f"\n Capacity vs Peak: {131 - max_dem:.2f} MW margin")
