i have created two files one is main.py which has the main logic and other app.py
in which we have created a basic app out of logic
 here is the tkinter guide >

 > 🚀 Step 1: Create Your First Window
✅ Code
import tkinter as tk

root = tk.Tk()
root.mainloop()

🔍 Explanation
Line	Meaning
tk.Tk()	creates window
mainloop()	keeps window running

👉 Without mainloop(), window closes instantly.

🎨 Step 2: Set Window Title & Size
import tkinter as tk

root = tk.Tk()
root.title("My First App")
root.geometry("400x300")

root.mainloop()

geometry format:
width x height

🧱 Step 3: Add Text (Label)
label = tk.Label(root, text="Hello Ali!")
label.pack()

pack() → places widget in window
🧱 Step 4: Add Button
def clicked():
    print("Button clicked")

button = tk.Button(root, text="Click Me", command=clicked)
button.pack()

command = function to run when clicked
🧱 Step 5: Add Input Field (Entry)
entry = tk.Entry(root)
entry.pack()


To get text:

text = entry.get()

🧱 Step 6: Show Message Popup
from tkinter import messagebox

messagebox.showinfo("Title", "Hello!")

🧱 Step 7: Arrange Layout (Important)

Tkinter has 3 layout managers:

✅ 1️⃣ pack() → simplest

Stacks widgets vertically.

✅ 2️⃣ grid() → rows & columns

Best for forms.

✅ 3️⃣ place() → exact position

Advanced use.

Example using grid()
tk.Label(root, text="Name").grid(row=0, column=0)
tk.Entry(root).grid(row=0, column=1)

🧱 Step 8: Change Colors & Fonts
label = tk.Label(root,
                 text="Hello",
                 bg="black",
                 fg="white",
                 font=("Arial", 16))
label.pack()

🧪 Full Example (Mini App)
import tkinter as tk
from tkinter import messagebox

def greet():
    name = entry.get()
    messagebox.showinfo("Welcome", f"Hello {name}")

root = tk.Tk()
root.title("Greeting App")
root.geometry("300x150")

tk.Label(root, text="Enter your name").pack()

entry = tk.Entry(root)
entry.pack()

tk.Button(root, text="Greet", command=greet).pack()

root.mainloop()