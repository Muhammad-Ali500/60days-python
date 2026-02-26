We have:

numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

for i in range(0, len(numbers), 3):
    print(numbers[i:i+3])
Step 1: Understanding range(0, len(numbers), 3)

len(numbers) = 10

range(0, 10, 3) → this produces the indices:

0, 3, 6, 9

Each number is where a slice starts.

Step 2: Iterating over numbers[i:i+3]
Iteration 1: i = 0

Slice: numbers[0:3]

Takes elements index 0, 1, 2 → [1, 2, 3]

Printed → [1, 2, 3]

Iteration 2: i = 3

Slice: numbers[3:6]

Takes elements index 3, 4, 5 → [4, 5, 6]

Printed → [4, 5, 6]

Iteration 3: i = 6

Slice: numbers[6:9]

Takes elements index 6, 7, 8 → [7, 8, 9]

Printed → [7, 8, 9]

Iteration 4: i = 9

Slice: numbers[9:12]

Only index 9 exists → [10]

Printed → [10]

Step 3: Why it works

Python slicing is safe even if the end index is larger than the list.

numbers[9:12] doesn’t error; it just takes whatever exists.

✅ That’s why the output is:

[1, 2, 3]
[4, 5, 6]
[7, 8, 9]
[10]