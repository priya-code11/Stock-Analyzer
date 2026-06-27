
import json
import pandas as pd
from google import genai
from google.genai import types
# Change this import statement at the top of agent.py
from .utils import get_historical_candles_helper


def fetch_indian_stock_metrics(symbol: str) -> str:
    """
    Fetches real-time market data, moving averages, and technical trends 
    for any Indian stock symbol to supply the AI agent with ground-truth numbers.
    """
    try:
        # Strip potential user input issues (like lowercase or exchange extensions)
        symbol = symbol.strip().upper().split(".")[0]
        
        # Pull 1-month daily historical data nodes using your optimized public engine
        candles_raw, latest_price = get_historical_candles_helper(symbol, "1M")
        
        if not candles_raw or len(candles_raw) < 2:
            return json.dumps({"error": f"Ticker '{symbol}' not found or has no active market sessions."})
            
        # Convert candle array elements cleanly into a DataFrame
        df = pd.DataFrame(candles_raw, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Date'])
        
        # Compute exact moving average thresholds
        df["MA20"] = df["Close"].rolling(window=min(20, len(df))).mean()
        df["MA50"] = df["Close"].rolling(window=min(50, len(df))).mean()
        
        latest = df.iloc[-1]
        prev_session = df.iloc[-2] if len(df) >= 2 else latest
        
        # Structure the payload text to guide the AI model's analytical layers
        market_summary = {
            "ticker_symbol": symbol,
            "current_market_price": round(float(latest["Close"]), 2),
            "previous_close_price": round(float(prev_session["Close"]), 2),
            "daily_change_points": round(float(latest["Close"] - prev_session["Close"]), 2),
            "moving_average_20_day": round(float(latest["MA20"]), 2) if not pd.isna(latest["MA20"]) else "Calculating...",
            "moving_average_50_day": round(float(latest["MA50"]), 2) if not pd.isna(latest["MA50"]) else "Calculating...",
            "immediate_trend": "UPWARD" if latest["Close"] >= prev_session["Close"] else "DOWNWARD"
        }
        
        return json.dumps(market_summary)
        
    except Exception as e:
        return json.dumps({"error": f"Data Pipeline Extraction Failure: {str(e)}"})


def execute_financial_agent(user_query: str) -> str:
    """
    Spawns an instance of the Gemini AI agent to analyze prompts, call native tools, 
    and output formatted investment insight reviews.
    """
    # Spawns a lightweight client instance referencing GEMINI_API_KEY
    client = genai.Client()
    
    # Declare the internal function tools available for the model to invoke
    available_tools = [fetch_indian_stock_metrics]
    
    system_rules = (
        "You are 'RupeeBot', an advanced AI Financial Analyst Agent specialized exclusively in the Indian Stock Markets (NSE/BSE).\n"
        "Your goal is to assist users with market research using concrete data metrics rather than speculative guessing.\n\n"
        "Core Directives:\n"
        "1. If a user names or asks about an Indian stock, you MUST immediately call the 'fetch_indian_stock_metrics' tool to retrieve live prices.\n"
        "2. Once you receive the JSON response, analyze the alignment between the current price and its 20/50 Day Moving Averages.\n"
        "3. Provide a structured review using Markdown formatting: state the current price trend, evaluate technical momentum, "
        "and present a sentiment perspective (e.g., Bullish Accumulation, Neutral Consolidation, Bearish Distribution).\n"
        "4. Always include a brief risk management disclaimer reminding users that you are an AI assistant, not a licensed SEBI advisor.\n"
        "5. Keep answers sharp, clear, and highly professional. Refuse to answer questions unrelated to finance or markets."
    )
    
    # We use gemini-2.5-flash since it offers rapid response latency and supports Function Calling natively
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=user_query,
        config=types.GenerateContentConfig(
            tools=available_tools,
            system_instruction=system_rules,
            temperature=0.2, # Lower temperature forces strictly disciplined analysis
        )
    )
    
    return response.text