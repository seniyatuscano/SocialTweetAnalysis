import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from twikit import Client
from google import genai

# ============================================
# CONFIG
# ============================================
_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_env_path)

# ============================================
# DATA MODELS
# ============================================
class TweetResponse(BaseModel):
    id: str
    text: str
    user_screen_name: str
    user_name: str
    user_profile_image_url: str
    favorite_count: int
    retweet_count: int
    tweet_url: str

class VibeSummaryResponse(BaseModel):
    url_searched: str
    tweet_count: int
    vibe_summary: str
    top_tweets: list[TweetResponse]

class UrlPayload(BaseModel):
    url: str

# ============================================
# CLIENTS
# ============================================
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
_twitter_client: Client | None = None

# ============================================
# LIFESPAN MANAGER
# ============================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _twitter_client
    _twitter_client = Client(language="en-US")
    print("✅ Twitter client initialized")
    yield
    _twitter_client = None
    print("🔴 Twitter client closed")

app = FastAPI(title="SocialBackchannel API", lifespan=lifespan)

# ============================================
# CORS MIDDLEWARE
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# UTILITY FUNCTIONS
# ============================================
async def ensure_logged_in(client: Client):
    """Ensures Twitter client is authenticated with cookies."""
    cookies_path = os.getenv("TWITTER_COOKIES", "cookies.json")
    
    if not os.path.isfile(cookies_path):
        raise HTTPException(status_code=401, detail="cookies.json missing.")
    
    try:
        with open(cookies_path, 'r') as f:
            cookies_data = json.load(f)
        
        client.load_cookies(cookies_path)
        
        # CRITICAL: Sync CSRF token for write/search operations
        if 'ct0' in cookies_data:
            client.set_cookies({'ct0': cookies_data['ct0']})
        
        print("✅ Twitter authentication successful")
    except Exception as e:
        print(f"❌ Cookie authentication failed: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid cookies: {str(e)}")

async def analyze_tweets_with_gemini(tweets: list) -> str:
    """Summarizes tweets using Gemini 2.5 Flash Lite."""
    tweets_text = "\n\n".join([f"@{t.user_screen_name}: {t.text}" for t in tweets])
    
    prompt = (
        "You are a social media analyst. Analyze the sentiment and key themes from these tweets.\n\n"
        "Return EXACTLY 3 bullet points:\n"
        "- Each point must be 10 words or less\n"
        "- Use professional, neutral language\n"
        "- Focus on: sentiment, controversy, common themes\n"
        "- Start each bullet with '•'\n\n"
        f"Tweets:\n{tweets_text}"
    )
    
    try:
        print("🤖 Sending tweets to Gemini for analysis...")
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash-lite", 
            contents=prompt
        )
        summary = response.text.strip()
        print(f"✅ Gemini analysis complete: {len(summary)} chars")
        return summary
    except Exception as e:
        print(f"❌ Gemini analysis failed: {e}")
        return f"• Analysis temporarily unavailable\n• Error: {str(e)}\n• Please try again"

# ============================================
# API ENDPOINTS
# ============================================
@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "SocialBackchannel API",
        "version": "1.0.0"
    }

@app.post("/url")
async def receive_url(payload: UrlPayload):
    """Legacy endpoint for receiving URLs."""
    return {"status": "success", "url": payload.url}

@app.get("/analyze", response_model=VibeSummaryResponse)
async def analyze_url(url: str = Query(...), count: int = 10):
    """
    Main analysis endpoint.
    
    Args:
        url: The article URL to analyze
        count: Number of tweets to fetch (default 10)
    
    Returns:
        VibeSummaryResponse with vibe summary and top tweets
    """
    print(f"\n{'='*60}")
    print(f"🔍 ANALYSIS REQUEST")
    print(f"{'='*60}")
    print(f"📎 URL: {url}")
    print(f"📊 Count: {count}")
    
    # Authenticate Twitter client
    await ensure_logged_in(_twitter_client)
    
    # ============================================
    # SLUG EXTRACTION (Fallback Strategy)
    # ============================================
    try:
        # Remove query parameters and fragments
        clean_url = url.split('?')[0].split('#')[0]
        parts = clean_url.rstrip('/').split('/')
        
        # Get the last meaningful part (usually the article slug)
        if len(parts) > 3:
            slug = parts[-1]
        elif len(parts) > 2:
            slug = parts[-2]
        else:
            slug = "news"
        
        # Clean and limit slug
        slug = slug.replace('-', ' ').replace('_', ' ')[:100]
        
        print(f"📝 Extracted slug: '{slug}'")
    except Exception as e:
        print(f"⚠️ Slug extraction failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid URL format")
    
    # ============================================
    # TWITTER SEARCH WITH TIMEOUT
    # ============================================
    try:
        print(f"🐦 Searching Twitter for: '{slug}'")
        
        result = await asyncio.wait_for(
            _twitter_client.search_tweet(query=slug, product="Top", count=count),
            timeout=25.0
        )
        
        tweets_list = list(result) if result else []
        print(f"✅ Found {len(tweets_list)} tweets")
        
    except asyncio.TimeoutError:
        print("⏱️ Twitter search timed out after 25 seconds")
        raise HTTPException(status_code=504, detail="Twitter search timed out after 25s")
    except Exception as e:
        print(f"❌ Twitter search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Twitter API error: {str(e)}")

    # Check if we found any tweets
    if not tweets_list:
        print(f"❌ No tweets found for slug: '{slug}'")
        raise HTTPException(status_code=404, detail=f"No tweets found for '{slug}'")
    
    # ============================================
    # EXTRACT FULL TWEET DATA
    # ============================================
    print(f"📦 Extracting tweet data...")
    responses = []
    
    for t in tweets_list:
        try:
            username = getattr(t.user, 'screen_name', 'user')
            tweet_id = str(t.id)
            
            # Extract profile image and upgrade to higher resolution
            profile_img = getattr(t.user, 'profile_image_url', '')
            if profile_img:
                # Replace _normal with _bigger for better quality
                profile_img = profile_img.replace('_normal', '_bigger')
            
            tweet_data = TweetResponse(
                id=tweet_id,
                text=t.text,
                user_screen_name=username,
                user_name=getattr(t.user, 'name', username),
                user_profile_image_url=profile_img,
                favorite_count=getattr(t, 'favorite_count', 0),
                retweet_count=getattr(t, 'retweet_count', 0),
                tweet_url=f"https://x.com/{username}/status/{tweet_id}"
            )
            
            responses.append(tweet_data)
        except Exception as e:
            print(f"⚠️ Failed to parse tweet {t.id}: {e}")
            continue
    
    print(f"✅ Successfully extracted {len(responses)} tweet objects")
    
    # ============================================
    # SELECT TOP TWEETS BY ENGAGEMENT
    # ============================================
    # Sort by total engagement (likes + retweets)
    top_tweets = sorted(
        responses, 
        key=lambda x: x.favorite_count + x.retweet_count, 
        reverse=True
    )[:2]  # Get top 2 most engaged tweets
    
    print(f"🏆 Selected top {len(top_tweets)} tweets by engagement:")
    for i, tweet in enumerate(top_tweets, 1):
        total_engagement = tweet.favorite_count + tweet.retweet_count
        print(f"   {i}. @{tweet.user_screen_name}: {total_engagement} engagements")
    
    # ============================================
    # GEMINI ANALYSIS
    # ============================================
    summary = await analyze_tweets_with_gemini(responses)
    
    # ============================================
    # RETURN RESPONSE
    # ============================================
    print(f"\n✅ Analysis complete!")
    print(f"{'='*60}\n")
    
    return VibeSummaryResponse(
        url_searched=url, 
        tweet_count=len(responses), 
        vibe_summary=summary,
        top_tweets=top_tweets
    )

# ============================================
# ERROR HANDLERS
# ============================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom error handler for better error messages."""
    return {
        "error": exc.detail,
        "status_code": exc.status_code
    }

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Catch-all error handler."""
    print(f"❌ Unexpected error: {str(exc)}")
    return {
        "error": "Internal server error",
        "detail": str(exc),
        "status_code": 500
    }

# ============================================
# STARTUP MESSAGE
# ============================================
if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🚀 Starting SocialBackchannel API")
    print("="*60)
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8000,
        timeout_keep_alive=60
    )