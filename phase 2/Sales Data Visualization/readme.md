🎯 1️⃣ Basic Workflow (MOST IMPORTANT)
import matplotlib.pyplot as plt

x = [1,2,3]
y = [10,20,15]

plt.plot(x, y)
plt.show()

What happens:

1️⃣ create data
2️⃣ plot
3️⃣ display

👉 This is the foundation of all charts.

📈 2️⃣ Line Plot (Trends)
plt.plot(x, y)
plt.title("Trend")
plt.xlabel("X Axis")
plt.ylabel("Y Axis")
plt.show()

Useful options
plt.plot(x, y, marker="o", linestyle="--")


Used for:
✔ trends
✔ time series
✔ performance monitoring

📊 3️⃣ Bar Chart
products = ["Laptop","Mouse","Keyboard"]
sales = [50, 120, 75]

plt.bar(products, sales)
plt.show()


Used for:
✔ comparisons
✔ revenue reports

🥧 4️⃣ Pie Chart
sizes = [40, 30, 30]
labels = ["A","B","C"]

plt.pie(sizes, labels=labels, autopct="%1.1f%%")
plt.show()


Used for:
✔ percentage distribution

📉 5️⃣ Histogram (Distribution)
data = [1,2,2,3,3,3,4,5]

plt.hist(data, bins=5)
plt.show()


Used for:
✔ data distribution
✔ ML preprocessing

🔵 6️⃣ Scatter Plot (Relationship)
x = [1,2,3,4]
y = [10,20,15,30]

plt.scatter(x, y)
plt.show()


Used for:
✔ correlation
✔ ML feature analysis

🎨 7️⃣ Customize Charts
Titles & Labels
plt.title("Sales Report")
plt.xlabel("Products")
plt.ylabel("Revenue")

Grid
plt.grid()

Legend
plt.plot(x,y,label="Sales")
plt.legend()

🎨 8️⃣ Colors & Styles
plt.plot(x, y, color="red")
plt.bar(products, sales, color="green")


Line styles:

linestyle="--"
marker="o"

📊 9️⃣ Multiple Lines in One Chart
plt.plot(x, y, label="2024")
plt.plot(x, [12,18,25], label="2025")
plt.legend()
plt.show()

🧱 🔟 Subplots (Multiple Charts)
plt.subplot(1,2,1)
plt.plot(x,y)
plt.title("Chart 1")

plt.subplot(1,2,2)
plt.bar(products,sales)
plt.title("Chart 2")

plt.show()


Used for dashboards.

💾 1️⃣1️⃣ Save Chart as Image
plt.savefig("chart.png")


👉 used in reports & automation.

📐 1️⃣2️⃣ Figure Size
plt.figure(figsize=(8,5))

🔄 1️⃣3️⃣ Clear / Reset Figure
plt.clf()   # clear figure
plt.close() # close window

🧮 1️⃣4️⃣ Axis Control
plt.xlim(0,10)
plt.ylim(0,50)

🧾 1️⃣5️⃣ Tick Rotation
plt.xticks(rotation=45)


Useful for dates.

⭐ MOST IMPORTANT FUNCTIONS (MEMORIZE)
Core plotting

✅ plot()
✅ bar()
✅ scatter()
✅ pie()
✅ hist()

Labels & formatting

✅ title()
✅ xlabel()
✅ ylabel()
✅ legend()
✅ grid()

Layout & control

✅ figure()
✅ subplot()
✅ savefig()
✅ show()