🐼 1️⃣ Creating & Loading Data
🔹 Create DataFrame
import pandas as pd

data = {"name": ["Ali", "Sara"], "age": [22, 21]}
df = pd.DataFrame(data)

🔹 Load files
pd.read_csv("file.csv")
pd.read_excel("file.xlsx")
pd.read_json("file.json")

🔹 Save files
df.to_csv("out.csv", index=False)
df.to_excel("out.xlsx", index=False)

🐼 2️⃣ Viewing & Understanding Data
df.head()        # first 5 rows
df.tail()        # last rows
df.shape         # (rows, columns)
df.columns       # column names
df.info()        # data types & nulls
df.describe()    # statistics


👉 Used in dataset inspection before ML.

🐼 3️⃣ Selecting Data
🔹 Select column
df["age"]
df[["name", "age"]]

🔹 Select rows
df.iloc[0]      # by position
df.loc[0]       # by label

🔹 Filter rows
df[df["age"] > 21]

🐼 4️⃣ Adding & Modifying Columns
df["salary"] = [500, 700]

df["age_plus_5"] = df["age"] + 5

🐼 5️⃣ Dropping Data
df.drop("salary", axis=1, inplace=True)  # drop column
df.drop(0, inplace=True)                 # drop row

🐼 6️⃣ Sorting Data
df.sort_values("age")
df.sort_values("age", ascending=False)

🐼 7️⃣ Handling Missing Data
df.isnull()
df.isnull().sum()

df.dropna()                # remove null rows
df.fillna(0)               # fill with value
df["age"].fillna(df["age"].mean())


👉 VERY important in AI preprocessing.

🐼 8️⃣ Aggregation & Statistics
df["age"].mean()
df["age"].sum()
df["age"].max()
df["age"].min()
df["age"].count()

🐼 9️⃣ Grouping Data (POWERFUL)
df.groupby("department")["salary"].sum()
df.groupby("department").mean()


👉 Used in business analytics & ML.

🐼 🔟 Value Counting & Frequency
df["department"].value_counts()


👉 useful for category distribution.

🐼 1️⃣1️⃣ Unique & Duplicate Data
df["department"].unique()
df["department"].nunique()

df.duplicated()
df.drop_duplicates()

🐼 1️⃣2️⃣ Apply Functions
df["age"].apply(lambda x: x + 1)


👉 apply custom logic to data.

🐼 1️⃣3️⃣ Working with Strings
df["name"].str.upper()
df["name"].str.contains("A")
df["name"].str.replace("Ali", "ALI")

🐼 1️⃣4️⃣ Working with Dates
df["date"] = pd.to_datetime(df["date"])

df["date"].dt.year
df["date"].dt.month


👉 used in trend & time-series analysis.

🐼 1️⃣5️⃣ Merging & Joining Data
pd.merge(df1, df2, on="id")


👉 combine datasets (very common).

🐼 1️⃣6️⃣ Pivot Tables (Excel Power)
pd.pivot_table(df, values="sales", index="product", aggfunc="sum")

🐼 1️⃣7️⃣ Renaming Columns
df.rename(columns={"old": "new"}, inplace=True)

🐼 1️⃣8️⃣ Iterating Rows (Rarely Needed)
for index, row in df.iterrows():
    print(row["age"])


⚠️ Avoid for large data — use vector operations.

🐼 1️⃣9️⃣ Exporting Results
df.to_csv("output.csv")
df.to_json("output.json")
