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


table=[df[['product', 'quantity', 'price', 'Revenue', 'sum_revenue', 'avg_revenue', 'max_revenue', 'min_revenue']]]
print (f"the table of products, quantity, price and revenue: \n{table}")

if os.path.exists('sales_analysis.csv'):
    print("sales_analysis.csv already exists. Do you want to overwrite it? (yes/no)")
    answer = input().lower()
    if answer == 'yes':
        df.to_csv('sales_analysis.csv', index=False)
        print("sales_analysis.csv has been overwritten.")
    else:
        print("sales_analysis.csv was not overwritten.")
else:
    df.to_csv('sales_analysis.csv', index=False)



