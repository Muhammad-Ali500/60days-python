import socket
import threading

def receive_messages(client_socket):
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if message.lower() == 'exit':
                print("Server has disconnected.")
                break
            print(f"Server: {message}")
        except:
            break

def send_messages(client_socket):
    while True:
        message = input(">>>- ")
        client_socket.send(message.encode('utf-8'))
        if message.lower() == 'exit':
            break

# Connect to server
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('127.0.0.1', 9999))
print("Connected to server on port 9999...")

# Start send and receive threads
threading.Thread(target=receive_messages, args=(client,), daemon=True).start()
threading.Thread(target=send_messages, args=(client,), daemon=True).start()

# Keep main thread alive
while True:
    pass
