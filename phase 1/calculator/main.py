while True:

    x = int(input("Enter a number: "))
    opertator = input("Enter an operator (+, -, *, /): ")
    y = int(input("Enter another number: "))

    def calculate_square(x,y):
        if opertator == "+":
            return x + y
        elif opertator == "-":
            return x - y
        elif opertator == "*":
            return x * y
        elif opertator == "/":
            if y != 0:
                return x / y
            else:
                return "Error: Division by zero is not allowed."
        else:
            return "Error: Invalid operator."

    result = calculate_square(x,y)
    print("Result:", result)