import psutil
import time

print("System Health Monitoring is started")

cpu = psutil.cpu_percent(interval=1)
print(f"CPU Usage:{cpu}%")
memory = psutil.virtual_memory()
print(f"Memory Usage: {memory.percent}%")
disk = psutil.disk_usage('/')   
print(f"Disk Usage: {disk.percent}%")
network = psutil.net_io_counters()
print(f"Network Sent: {network.bytes_sent} bytes")
print(f"Network Received: {network.bytes_recv} bytes")
