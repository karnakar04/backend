from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
from pymongo import MongoClient
from textblob import TextBlob
from datetime import datetime
from bson import ObjectId
from collections import defaultdict
from fastapi.responses import JSONResponse

app = FastAPI()

# Allow specific frontend origins
origins = [
    "*" # Allow all origins
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request model
class QueryModel(BaseModel):
    user_query: str

class SentimentRequest(BaseModel):
    text: str

# Gemini AI API Key (Replace with your actual key)
API_KEY = "AIzaSyCBPmyFz7wqbrJPUKZSsqkH91mC0lg0Rp0"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"


# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://karnakar5511:p8Vy0UVjvy7pciOH@cluster0.xr3ih5b.mongodb.net/")

client = MongoClient(MONGO_URI)
db = client.get_database("gemini_analysis")
collection = db.get_collection("queries")


# Function for Sentiment Analysis
def get_sentiment(text):
    analysis = TextBlob(text)
    sentiment_score = analysis.sentiment.polarity  # Ranges from -1 to 1
    sentiment = "Positive 😀" if sentiment_score > 0 else "Negative 😡" if sentiment_score < 0 else "Neutral 😐"
    return sentiment_score, sentiment


@app.post("/sentiment")
async def analyze_sentiment(request: SentimentRequest):
    sentiment_score, sentiment = get_sentiment(request.text)
    return {
        "text": request.text,
        "sentiment_score": sentiment_score,
        "sentiment": sentiment
    }




@app.post("/analyze")
async def analyze_text(request: QueryModel):
    user_query = request.user_query

    # Get sentiment analysis

    # Proper API request format
    data = {
        "contents": [{"parts": [{"text": user_query}]}]
    }

    try:
        # Send request to Gemini API
        response = requests.post(API_URL, json=data)
        response.raise_for_status()  # Raise an error for 4xx/5xx responses

        # Extract AI response safely
        response_data = response.json()
        generated_text = (
            response_data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "No response received.")
        )
        sentiment_score, sentiment = get_sentiment(user_query)
        # Save the query to the database
        collection.insert_one({"user_query": user_query,"generated_text":generated_text , "sentiment_score": sentiment_score,"sentiment": sentiment,"timestamp": datetime.utcnow().isoformat()})
        return {
            "user_query": user_query,
           
            "generated_text": generated_text
        }

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"API Request Failed: {str(e)}")

    except KeyError:
        raise HTTPException(status_code=500, detail="Unexpected API response format")

    # Check if the query exists in the database
    # query_data = collection.find_one({"user_query
@app.get("/query-trends")
async def get_query_trends():
    res = collection.find({})
    trends = defaultdict(int)  # Dictionary to store {date: count}

    for doc in res:
        timestamp = doc.get("timestamp")  # Ensure 'timestamp' exists
        if timestamp:
            date_str = timestamp.split("T")[0]  # Extract YYYY-MM-DD
            trends[date_str] += 1 # Increment count for the date

    # Convert to list of dicts for React
    return [{"date": date, "query_count": count} for date, count in trends.items()]   




@app.get("/query-category-distribution")
async def get_query_category_distribution():
    res = collection.find({})
    category_distribution = defaultdict(int)

    for doc in res:
        sentiment = doc.get("sentiment")
        category_distribution[sentiment] += 1
        
        #converting dictionary to array of objects
        
    formatted_data = [{"category": k, "count": v} for k, v in category_distribution.items()]
    return formatted_data

@app.get("/user-engagement")
async def get_user_engagement():
    res = collection.find({})
    user_engagement = defaultdict(int)

    for doc in res:
        user_query = doc.get("user_query", "Unknown")  # Default to "Unknown" if key is missing
        user_engagement[user_query] += 1

    # Convert to a JSON-friendly format
    engagement_list = [{"user_query": key, "count": value} for key, value in user_engagement.items()]

    return JSONResponse(content=engagement_list)


@app.get("/")
def home():
    return {"message": "FastAPI is running!"}



# Run FastAPI server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)
