import socket

Host = input("Enter the target host IP address: ")

ports =[21, 22, 23, 25, 53, 80, 110, 143,135, 443, 3306]

print(f"Scanning ports on {Host}...")

for port in ports:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((Host, port))
    if result == 0:
        print(f"Port {port} is open.")
    else:
        print(f"Port {port} is closed.")
        