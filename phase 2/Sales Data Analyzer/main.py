with open("sales.csv", "r") as file:
    content = file.read()

quantity = []
price = []
products = []
revenue = []

for x in range (1, len(content.splitlines())):
    line = content.splitlines()[x]
    values = line.split(",")
#    print(values[2],values[3]) 
    
    quantity.append(float(values[2]))
    price.append(float(values[3]))
    products.append(values[1])
print(price)
print(quantity)
print(products)
total_price = sum(price) 
print(f"Total sum of price is : {total_price}")

avg_price = total_price / len(price) 
print(f"the Average price: {avg_price}")
   
max_price = max(price)
print(f"the maximum price: {max_price} ,product: {products[price.index(max_price)]}")

min_price = min(price)
print(f"the minimum price: {min_price} ,product: {products[price.index(min_price)]}")

total_revenue = sum([quantity[i] * price[i] for i in range(len(quantity))])
print(f"Total revenue: {total_revenue}")