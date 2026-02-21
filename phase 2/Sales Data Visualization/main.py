import pandas as pd
import matplotlib.pyplot as plt
import os

df = pd.read_csv('sales.csv')

df['Revenue'] = df['quantity'] * df['price']
#print(f"the total revenue per product: \n{df[['product', 'Revenue']]}")

df['sum_revenue'] = df.groupby('product')['Revenue'].transform('sum')
#print(f"the total revenue per product: \n{df[['product', 'sum_revenue']].drop_duplicates()}")

df['avg_revenue'] = df.groupby('product')['Revenue'].transform('mean')
#print(f"the average revenue per product: \n{df[['product', 'avg_revenue']].drop_duplicates()}")

df['max_revenue'] = df.groupby('product')['Revenue'].transform('max')
#print(f"the maximum revenue per product: \n{df[['product', 'max_revenue']].drop_duplicates()}")

df['min_revenue'] = df.groupby('product')['Revenue'].transform('min')
#print(f"the minimum revenue per product: \n{df[['product', 'min_revenue']].drop_duplicates()}")


x= df['product']
y= df['Revenue']

plt.figure(figsize=(10,6))
plt.bar(x, y, color='blue')
plt.title('Revenue per Product')
plt.xlabel('Product')
plt.ylabel('Revenue')
#plt.xticks(rotation=45)
plt.grid()  
#plt.tight_layout()
plt.show()
