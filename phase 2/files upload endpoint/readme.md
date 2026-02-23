🔹 1. What does async mean?

async allows a function to run without blocking other tasks.

👉 Normal function:

def my_function():

Runs step by step

Blocks other operations until finished

👉 Async function:

async def my_function():

Can pause and let other tasks run

Improves performance for I/O tasks (file upload, database, API calls)

💡 Think of it like:

Instead of standing idle while waiting, the program does other work.

🔹 2. What does await mean?

await tells Python:

👉 “Pause here until this task finishes, but don’t block everything else.”

Example:

contents = await file.read()

Meaning:

Start reading file

While reading → server can handle other requests

Resume when file is ready

Without await, the server would freeze while reading.

🔹 3. Why async is important in APIs

APIs handle many users at the same time.

If 100 users upload files:

❌ Without async
→ users wait in line

✅ With async
→ server handles multiple uploads simultaneously

That’s why FastAPI uses async by default.

🔹 4. How your function works step-by-step
✔ Step 1: Create app
app = FastAPI()

Creates the API server.

✔ Step 2: Create upload endpoint
@app.post("/upload")

When user sends POST request to:

/upload

this function runs.

✔ Step 3: Function definition
async def upload_file(file: UploadFile = File(...)):

What this means:

async → non-blocking function

file → file uploaded by user

UploadFile → FastAPI file object

File(...) → required file input

✔ Step 4: Read file content
contents = await file.read()

Flow:

Server starts reading file

While reading → handles other users

When done → stores data in contents

✔ Step 5: Return response
return {
    "filename": file.filename,
    "content_type": file.content_type,
    "size": len(contents)
}

Returns:

file name

file type

file size

🔹 5. Example Request

Using curl:

curl -X POST "http://127.0.0.1:8000/upload" \
 -H "Content-Type: multipart/form-data" \
 -F "file=@test.txt"
Response:
{
  "filename": "test.txt",
  "content_type": "text/plain",
  "size": 1024
}
🔹 6. Why FastAPI uses async for file uploads

File reading is I/O operation:

disk access

network upload

waiting time involved

Async prevents server slowdown.

🔹 7. When should YOU use async?

Use async when:

✅ reading files
✅ database queries
✅ calling APIs
✅ waiting operations

Avoid async when:

❌ heavy CPU calculations
❌ simple math tasks

🔹 8. Real-world analogy

Imagine a shopkeeper:

Without async
He serves one customer completely before the next.

With async
He starts preparing one order, takes another order while waiting.