from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator
import torch
import uvicorn
import re

model_name = "sshleifer/distilbart-cnn-12-6"

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

#we can chose gpu device if available else it will work on cpu
model.eval()
device = "cuda"  if torch.cuda.is_available() else "cpu"
model.device

app = FastAPI()


# -------- CHUNKING FUNCTION ----------
def chunk_text(text, max_tokens=800):
    tokens = tokenizer.encode(text)
    chunks = []

    for i in range(0, len(tokens), max_tokens):
        chunk = tokens[i:i + max_tokens]
        chunks.append(tokenizer.decode(chunk))

    return chunks

class SummarizationText(BaseModel):
    text: str
    max_length: int = 60
    min_length: int = 25

def summarize_chunk(text: str, max_length: int, min_length: int) -> str:

    text= re.sub(r'\s+', ' ', text).strip()

    inputs = tokenizer(
        text,
        return_tensors="pt",
        max_length=1024,
        truncation=True
    )
#this step it will no commpute gradients if we chose torch.no_grad  
    with torch.no_grad():
     summary_ids = model.generate(
        inputs["input_ids"],
        max_length=max_length,
        min_length=min_length,
        length_penalty=2.0,
        num_beams=4,
        early_stopping=True
    )

    return tokenizer.decode(summary_ids[0], skip_special_tokens=True)

# -------- FULL PIPELINE ----------
def summarize_large_text(text):
    chunks = chunk_text(text)

    chunk_summaries = []
    for chunk in chunks:
        chunk_summaries.append(summarize_chunk(chunk))

    combined_summary = " ".join(chunk_summaries)

    # Final summary pass (optional but recommended)
    if len(chunk_summaries) > 1:
        final_summary = summarize_chunk(combined_summary)
        return final_summary

    return combined_summary

@app.post("/summarization")
async def summarize(payload: SummarizationText):
    try:
        summary = summarize_chunk(payload.text, payload.max_length, payload.min_length)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)