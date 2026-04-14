from django.shortcuts import render,HttpResponse
import pandas as pd
import yfinance as yf



# Create your views here.
def index(request):
    context = {
        'var': "this is variable "
    }
    return render(request,'index.html',context)

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
    # 🇮🇳 Indian Stocks (NSE)
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "SBIN.NS",
    "ITC.NS",
    "LT.NS",
    "AXISBANK.NS",
    "KOTAKBANK.NS",
    "BHARTIARTL.NS",
    "ASIANPAINT.NS",
    "MARUTI.NS",
    "TITAN.NS",
    "ULTRACEMCO.NS",

    # 🇺🇸 US Stocks
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "TSLA",
    "META",
    "NFLX",
    "NVDA",

    # 💰 Crypto (optional - works in yfinance)
    "BTC-USD",
    "ETH-USD"
]

    results = []

    for symbol in stocks_list:
        stock = yf.Ticker(symbol)
        data = stock.history(period="5d")   # last few days

        price = data['Close'].iloc[-1]
        prev_price = data['Close'].iloc[-2]

        change = price - prev_price

        if change > 0:
            trend = "UP"
        else:
            trend = "DOWN"

        results.append({
            "symbol": symbol,
            "price": round(price, 2),
            "change": round(change, 2),
            "trend": trend
        })

    return render(request, "market_trends.html", {"stocks": results})

def portfolio(request):
    return render(request,'portfolio.html')