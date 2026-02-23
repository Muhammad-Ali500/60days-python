from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

model_name = "sshleifer/distilbart-cnn-6-6"

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
app = FastAPI()

# Define request model
class SummarizeRequest(BaseModel):
    text: str

def summarize_text(text):
    inputs = tokenizer(
        text, return_tensors="pt", truncation=True, padding=True, max_length=1024
    )
    summary_ids = model.generate(
        inputs["input_ids"],
        max_length=150,
        min_length=40,
        length_penalty=2.0,
        num_beams=4,
        early_stopping=True
    )
    return tokenizer.decode(summary_ids[0], skip_special_tokens=True)

@app.post("/summarize")
async def summarize(payload: SummarizeRequest):
    summary = summarize_text(payload.text)
    return {"summary": summary}

if __name__ == "__main__":
    text = input("Enter text to summarize (leave empty to start API): ").strip()
    if text:
        print("Summary:", summarize_text(text))
    else:
        uvicorn.run("main:app", host="127.0.0.1", port=8000)
