from transformers import AutoTokenizer, AutoModelForSequenceClassification
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import torch

model_name = "tabularisai/multilingual-sentiment-analysis"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForSequenceClassification.from_pretrained(model_name)
device = "cuda" if torch.cuda.is_available() else "cpu"
model.to(device)

def predict_sentiment(texts):
    inputs = tokenizer(texts, return_tensors="pt", truncation=True, padding=True, max_length=512)
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
    probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
    sentiment_map = {0: "Very Negative", 1: "Negative", 2: "Neutral", 3: "Positive", 4: "Very Positive"}
    return [sentiment_map[p] for p in torch.argmax(probabilities, dim=-1).tolist()]

app = FastAPI()

class SentimentRequest(BaseModel):
    text: str

@app.post("/sentiment")
async def analyze_sentiment(payload: SentimentRequest):
    sentiment = predict_sentiment([payload.text])[0]
    return {"text": payload.text, "sentiment": sentiment}

if __name__ == "__main__":
    texts = input("Enter comma-separated texts for sentiment analysis (leave empty to start API): ").strip()
    if texts:
        texts = [t.strip() for t in texts.split(",") if t.strip()]
        for text, sentiment in zip(texts, predict_sentiment(texts)):
            print(f"Text: {text}\nSentiment: {sentiment}\n")
    else:
        uvicorn.run("main:app", host="127.0.0.1", port=8000)