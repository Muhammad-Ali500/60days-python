import random

generate_password = input("Do you want to generate a random password? (yes/no): ")
if generate_password.lower() == "yes":
    print ("select the stength of the password")
    
stength = input("Enter the strength of the password (weak, medium, strong): ")
if stength.lower() == "weak":
    characters = "abcdefghijklmnopqrstuvwxyz"
elif stength.lower() == "medium":
    characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"       
elif stength.lower() == "strong":   
    characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()"
else:    print("Invalid strength option. Please choose weak, medium, or strong.")
password_length = int(input("Enter the desired password length: "))
password = "".join(random.choice(characters) for _ in range(password_length))
print("Generated password:", password)