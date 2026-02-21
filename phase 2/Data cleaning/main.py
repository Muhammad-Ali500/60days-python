import pandas as pd

# ===============================
# 1️⃣ Load Data
# ===============================
df = pd.read_csv("raw_data.txt")  # or "dirty_data.csv"
print("Original Data:\n", df.head())

# ===============================
# 2️⃣ Clean Numeric Columns
# ===============================
# Convert to numeric, invalid entries become NaN
numeric_cols = ['quantity', 'price', 'discount']
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# ===============================
# 3️⃣ Clean Text Columns
# ===============================
# Fill missing product names
df['product'].fillna('Unknown', inplace=True)

# Strip extra spaces
df['product'] = df['product'].str.strip()

# ===============================
# 4️⃣ Handle Date Column
# ===============================
# Convert to datetime
df['date'] = pd.to_datetime(df['date'], errors='coerce')

# Forward-fill missing dates
df['date'].ffill(inplace=True)

# ===============================
# 5️⃣ Handle Missing Numeric Values
# ===============================
# Fill missing values
df['quantity'].fillna(df['quantity'].median(), inplace=True)
df['price'].fillna(df['price'].mean(), inplace=True)
df['discount'].fillna(0, inplace=True)
print(df)

# ===============================
# 6️⃣ Remove Duplicates
# ===============================
df.drop_duplicates(inplace=True, keep='first')
print(df)
# ===============================
# 7️⃣ Optional: Detect & Replace Garbage Strings
# ===============================
garbage_strings = ["abc", "xyz", "???", "--"]
df.replace(garbage_strings, pd.NA, inplace=True)

# Fill resulting NaN if needed
df.fillna({
    'quantity': df['quantity'].median(),
    'price': df['price'].mean(),
    'discount': 0,
    'product': 'Unknown'
}, inplace=True)

# ===============================
# 8️⃣ Reset Index
# ===============================
df.reset_index(drop=True, inplace=True)

# ===============================
# 9️⃣ Save Cleaned Data
# ===============================
df.to_csv("cleaned_data.csv", index=False)
print("\n✅ Data cleaned and saved as 'cleaned_data.csv'")

# ===============================
# 10️⃣ Preview Cleaned Data
# ===============================
print("\nCleaned Data Preview:\n", df.head(10))
