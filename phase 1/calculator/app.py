import tkinter as tk
from tkinter import messagebox

def calculate():
    try:
        x = float(entry1.get())
        y = float(entry2.get())
        operator = operator_var.get()

        if operator == "+":
            result = x + y
        elif operator == "-":
            result = x - y
        elif operator == "*":
            result = x * y
        elif operator == "/":
            if y != 0:
                result = x / y
            else:
                result = "Division by zero!"
        else:
            result = "Invalid operator"

        result_label.config(text=f"Result: {result}")

    except ValueError:
        messagebox.showerror("Error", "Please enter valid numbers")

# window
root = tk.Tk()
root.title("Calculator")
root.geometry("300x250")

tk.Label(root, text="First Number").pack()
entry1 = tk.Entry(root)
entry1.pack()

tk.Label(root, text="Operator").pack()

operator_var = tk.StringVar(value="+")
tk.OptionMenu(root, operator_var, "+", "-", "*", "/").pack()

tk.Label(root, text="Second Number").pack()
entry2 = tk.Entry(root)
entry2.pack()

tk.Button(root, text="Calculate", command=calculate).pack(pady=10)

result_label = tk.Label(root, text="")
result_label.pack()

root.mainloop()
