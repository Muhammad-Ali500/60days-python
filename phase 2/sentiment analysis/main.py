from fastapi import FastAPI
from pydantic import BaseModel
from pandas import DataFrame
import pandas as pd
import uvicorn
import re

#positive_words = {
#    "good", "great", "excellent", "amazing", "happy",
#    "love", "fast", "awesome", "fantastic", "enjoyable"
#}

#negative_words = {
#    "bad", "terrible", "slow", "boring", "worst",
#    "sad", "hate", "poor", "awful", "noisy"
#}
positive_words = set(pd.read_csv("+data.csv", header=None)[0].str.strip().str.lower())
negative_words = set(pd.read_csv("-data.csv", header=None)[0].str.strip().str.lower())



def analyze_sentiment(text: str) -> str:
    words = re.findall(r"\b\w+\b", text.lower())
    positive_count = sum(w in positive_words for w in words)
    negative_count = sum(w in negative_words for w in words)
    if positive_count > negative_count:
        return "positive"
    elif negative_count > positive_count:
        return "negative"
    else:
        return "neutral"

app = FastAPI()

class TextPayload(BaseModel):
    text: str

@app.get("/sentiment")
def get_sentiment(text: str):
    words = re.findall(r"\b\w+\b", text.lower())
    return {
        "sentiment": analyze_sentiment(text),
        "positive_count": sum(w in positive_words for w in words),
        "negative_count": sum(w in negative_words for w in words)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)