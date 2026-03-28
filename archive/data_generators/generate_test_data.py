import pandas as pd

# Load the 1-week data
df = pd.read_csv('data/Import_Data.csv')
df['Datum'] = pd.to_datetime(df['Datum'])

# Create just 1 day (24 hours)
one_day = df.iloc[:24].copy()

# Generate dates for 1 day
new_dates = pd.date_range(start='2023-01-01', periods=24, freq='h')
one_day['Datum'] = new_dates

# Save
one_day.to_csv('data/Import_Data_test_1day.csv', index=False)
print(f"Created test data: {len(one_day)} rows (1 day)")
