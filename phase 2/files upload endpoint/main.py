from importlib.resources import contents
from fastapi import FastAPI, File, UploadFile
import uvicorn
import os

if not os.path.exists("uploads"):
    os.makedirs("uploads")
app = FastAPI()
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    save_path = os.path.join("uploads", file.filename)
    with open(save_path, "wb") as f:
        f.write(contents)
    return {"filename": file.filename, "content_type": file.content_type, "size": len(contents)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)         