todo_list = []

def add_todo(todo):
    with open("todo.txt", "a") as file:
        file.write(todo + "\n")

while True:
    todo = input("What do you need to do? (type 'exit' to stop): ")

    if todo.lower() == "exit":
        break

    todo_list.append(todo)
    add_todo(todo)

    print("\nYou need to:")
    for task in todo_list:
        print("-", task)
