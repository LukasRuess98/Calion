import pandas as pd

# Load the 1-week data
df = pd.read_csv('data/Import_Data.csv')
df['Datum'] = pd.to_datetime(df['Datum'])

# Create a full year by repeating the 7-day pattern 52 times
full_year = pd.concat([df.copy() for _ in range(52)], ignore_index=True)

# Generate new dates spanning exactly one year (2023-01-01 to 2023-12-31)
new_dates = pd.date_range(start='2023-01-01', periods=len(full_year), freq='h')
full_year['Datum'] = new_dates

# Save the yearly data
full_year.to_csv('data/Import_Data_yearly.csv', index=False)
print(f"✓ Generated yearly data: {len(full_year)} rows ({len(full_year)/24:.0f} days)")
