from fastapi import FastAPI, File, UploadFile
from faster_whisper import WhisperModel
import uvicorn
import os


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()
model = WhisperModel("small", device="cpu") 

def transcribe_audio(file_path):
    segments, info = model.transcribe(file_path)
    transcription = " ".join([segment.text for segment in segments])
    return transcription

@app.post("/transcribe")
async def upload_and_transcribe(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    text = transcribe_audio(file_path)

    return {"filename": file.filename, "transcription": text}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)