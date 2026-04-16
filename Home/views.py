from django.shortcuts import render,HttpResponse
import pandas as pd
import yfinance as yf
import json


def index(request):

    symbol = "RELIANCE.NS"

    if request.method == "POST":
        symbol = request.POST.get("stock")

    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period="7d")

        if df is None or df.empty or len(df) < 2:
            raise ValueError("No data found")

        price = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        volume = df['Volume'].iloc[-1]

        trend = "UP" if price > prev else "DOWN"

        data = []
        for i in range(len(df)):
            data.append({
                "date": df.index[i].strftime("%d %b"),
                "open": round(df['Open'].iloc[i], 2),
                "close": round(df['Close'].iloc[i], 2),
                "high": round(df['High'].iloc[i], 2),
                "low": round(df['Low'].iloc[i], 2),
            })

        labels = [d["date"] for d in data]
        prices = [d["close"] for d in data]

        context = {
            "price": round(price, 2),
            "volume": volume,
            "trend": trend,
            "data": data,
            "labels": json.dumps(labels),
            "prices": json.dumps(prices)
        }

    except Exception as e:
        print("ERROR in index():", e)

        # ✅ SAFE FALLBACK
        context = {
            "price": 0,
            "volume": 0,
            "trend": "DOWN",
            "data": [],
            "labels": "[]",
            "prices": "[]"
        }

    return render(request, "index.html", context)

def about(request):
    return render(request,'about.html')

def calculate_rsi(data, period=14):
    delta = data['Close'].diff()

    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def prediction_view(request):
    result = None
    confidence = None
    stock_data = None
    error = None
    symbol = None

    if request.method == 'POST':
        symbol = request.POST.get('stock')

        try:
            stock = yf.Ticker(symbol)
            data = stock.history(period="3mo")

            if data.empty:
                error = "Invalid stock symbol (Use RELIANCE.NS)"
            else:
                data['MA20'] = data['Close'].rolling(window=20).mean()
                data['RSI'] = calculate_rsi(data)

                latest = data.iloc[-1]

                if pd.isna(latest['MA20']) or pd.isna(latest['RSI']):
                    error = "Not enough data"
                else:
                    price = latest['Close']
                    ma20 = latest['MA20']
                    rsi = latest['RSI']

                    stock_data = {
                        "price": round(price, 2),
                        "ma20": round(ma20, 2),
                        "rsi": round(rsi, 2)
                    }

                    if price > ma20 and rsi < 70:
                        result = "BUY"
                        confidence = "75%"
                    elif price < ma20 and rsi > 30:
                        result = "SELL"
                        confidence = "70%"
                    else:
                        result = "HOLD"
                        confidence = "60%"

        except Exception as e:
            error = str(e)

    return render(request, 'prediction.html', {
        'name':symbol,
        'prediction': result,
        'confidence': confidence,
        'stock': stock_data,
        'error': error
    })

def market_trends(request):
    stocks_list = [
        # 🇮🇳 Indian Stocks
        "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
        "SBIN.NS","ITC.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS",
        "BHARTIARTL.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS","ULTRACEMCO.NS",

        # 🇺🇸 US Stocks
        "AAPL","MSFT","GOOGL","AMZN","TSLA","META","NFLX","NVDA",

        # 💰 Crypto
        "BTC-USD","ETH-USD"
    ]

    results = []

    for symbol in stocks_list:
        try:
            stock = yf.Ticker(symbol)
            data = stock.history(period="5d")

            # ✅ Safety check
            if data is None or data.empty or len(data) < 2:
                continue

            price = data['Close'].iloc[-1]
            prev_price = data['Close'].iloc[-2]

            change = price - prev_price
            trend = "UP" if change > 0 else "DOWN"

            results.append({
                "symbol": symbol,
                "price": round(price, 2),
                "change": round(change, 2),
                "trend": trend
            })

        except Exception as e:
            print(f"Error in {symbol}: {e}")  # Debug
            continue   # skip bad stock

    return render(request, "market_trends.html", {"stocks": results})

