import socket
import threading

def receive_messages(client_socket):
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if message.lower() == 'exit':
                print("Client has disconnected.")
                break
            print(f"Client: {message}")
        except:
            break

def send_messages(client_socket):
    while True:
        message = input(">>>- ")
        client_socket.send(message.encode('utf-8'))
        if message.lower() == 'exit':
            break

# Set up server
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('127.0.0.1', 9999))
server.listen(1)
print("Server is listening on port 9999...")

client_socket, addr = server.accept()
print(f"New connection from {addr}")
client_socket.send("Welcome to the chat server!".encode('utf-8'))

# Start send and receive threads
threading.Thread(target=receive_messages, args=(client_socket,), daemon=True).start()
threading.Thread(target=send_messages, args=(client_socket,), daemon=True).start()

# Keep main thread alive
while True:
    pass
