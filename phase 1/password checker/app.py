import tkinter as tk

def check_password():
    password = entry.get()

    if len(password) < 8:
        result_label.config(text="At least 8 characters", fg="red")

    elif not any(char.isdigit() for char in password):
        result_label.config(text="Add a number", fg="red")

    elif not any(char.isupper() for char in password):
        result_label.config(text="Add uppercase letter", fg="red")

    elif not any(char.islower() for char in password):
        result_label.config(text="Add lowercase letter", fg="red")

    elif not any(char in "!@#$%^&*()_+-~" for char in password):
        result_label.config(text="Add special character", fg="red")

    else:
        result_label.config(text="Strong Password ✓", fg="green")

# window
root = tk.Tk()
root.title("Password Checker")
root.geometry("350x180")

tk.Label(root, text="Enter Password").pack(pady=5)

entry = tk.Entry(root, show="*", width=30)
entry.pack(pady=5)

tk.Button(root, text="Check", command=check_password).pack(pady=10)

result_label = tk.Label(root, text="")
result_label.pack()

root.mainloop()
