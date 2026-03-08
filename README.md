# Social Tweet Analysis 🌐

A Chrome Extension that overlays real-time, AI-synthesized social context on any URL you visit. Stop browsing in a vacuum and see what the internet is actually saying about the page you're reading.

## Architecture
* **Frontend:** Chrome Extension (Manifest V3) with asynchronous Service Workers to prevent UI blocking. UI designed with Stitch.
* **Backend:** Python FastAPI server handling high-concurrency scraping.
* **Intelligence:** Google Gemini 2.5 Flash Lite for instant sentiment analysis and toxicity filtering.

## How to Run Locally
1. Clone the repo: `git clone [https://github.com/seniyatuscano/SocialTweetAnalysis]`
2. Navigate to the backend: `cd backend`
3. Install dependencies: `pip install -r requirements.txt`
4. Add your secrets: Create a `.env` file with `GEMINI_API_KEY=your_key` and add your Twitter `cookies.json`.
5. Start the engine: `uvicorn main:app --host 127.0.0.1 --port 8000 --reload`
6. Load the `extension/` folder in `chrome://extensions/` as an unpacked extension.
