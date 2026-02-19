import requests
import json
import matplotlib.pyplot as plt
import pandas as pd

x = float(input("Enter logitude: "))
y = float(input("Enter latitude: "))
api_key = (f"https://api.open-meteo.com/v1/forecast?latitude={y}&longitude={x}&hourly=temperature_2m,rain")
response = requests.get(api_key)
data = json.loads(response.text)

hourly = data['hourly']
times = hourly['time']
temperatures = hourly['temperature_2m']
rain = hourly['rain']

# Print in a readable table-like format
for t, temp, r in zip(times, temperatures, rain):
    print(f"{t} | Temp: {temp}°C | Rain: {r}mm")


df = pd.DataFrame({
    "Time": times,
    "Temperature (°C)": temperatures,
    "Rain (mm)": rain
})

print(df)

plt.figure(figsize=(10,5))             # Set size of the graph
plt.plot(df['Time'], df['Temperature (°C)'], marker='o', color='red')
plt.title("Hourly Temperature")
plt.xlabel("Time")
plt.ylabel("Temperature (°C)")
plt.xticks(rotation=45)                 # Rotate x-axis labels for readability
plt.grid(True)
plt.show()

