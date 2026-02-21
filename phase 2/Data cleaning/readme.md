🐼 1️⃣ Load Data

Start with a messy CSV:

import pandas as pd

df = pd.read_csv("dirty_sales.csv")
print(df)


Example dirty_sales.csv:

product,quantity,price
Laptop,2,900
Mouse,,20
Keyboard,3,
Laptop,2,900
Monitor,1,300
Mouse,abc,20
Keyboard,4,50


Notice the issues:

Missing values

Invalid numeric entries (abc)

Duplicates

🐼 2️⃣ Inspect Data
df.info()       # shows data types and null counts
df.isnull().sum()  # count of missing values per column
df.head()       # preview first rows

🐼 3️⃣ Handle Missing Values
Option 1: Remove rows with missing data
df.dropna(inplace=True)

Option 2: Fill missing values
df["quantity"].fillna(df["quantity"].median(), inplace=True)
df["price"].fillna(df["price"].mean(), inplace=True)


median() is robust for quantities

mean() is common for price

🐼 4️⃣ Handle Invalid Data

Convert columns to numeric:

df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
df["price"] = pd.to_numeric(df["price"], errors="coerce")


Invalid entries (like "abc") become NaN

Then handle them with dropna() or fillna()

🐼 5️⃣ Remove Duplicates
df.drop_duplicates(inplace=True)


Prevents double-counting

🐼 6️⃣ Remove Outliers (Optional)
df = df[df["price"] < 1000]  # remove unrealistic prices
df = df[df["quantity"] < 100] # remove unrealistic quantities

🐼 7️⃣ Strip Extra Spaces (Text Columns)
df["product"] = df["product"].str.strip()

🐼 8️⃣ Reset Index
df.reset_index(drop=True, inplace=True)


Keeps the DataFrame clean after dropping rows.

🐼 9️⃣ Save Clean Data
df.to_csv("cleaned_sales.csv", index=False)

🧠 Why This Matters

✅ AI & ML → clean datasets give better models
✅ Analytics → accurate reports
✅ DevOps → reliable log monitoring
✅ Finance → correct calculations