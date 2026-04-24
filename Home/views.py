from django.shortcuts import render,HttpResponse
import pandas as pd
import yfinance as yf
import json

def index(request):

    # ✅ GET + POST support (IMPORTANT)
    symbol = request.GET.get("stock") or request.POST.get("stock") or "RELIANCE.NS"
    range_val = request.POST.get("range") or request.GET.get("range") or "7d"

    # ✅ BASE CONTEXT
    context = {
        "price": 0,
        "volume": 0,
        "trend": "DOWN",
        "data": [],
        "labels": "[]",
        "prices": "[]",
        "candles": "[]",
        "range": range_val,
        "symbol": symbol
    }

    try:
        stock = yf.Ticker(symbol)

        # ===== TIME LOGIC =====
        if range_val == "1d":
            df = stock.history(period="1d", interval="5m")
            date_format = "%H:%M"

        elif range_val == "7d":
            df = stock.history(period="7d", interval="1h")
            date_format = "%d %b %H:%M"

        elif range_val == "1mo":
            df = stock.history(period="1mo", interval="1d")
            date_format = "%d %b"

        elif range_val == "1y":
            df = stock.history(period="1y", interval="1wk")
            date_format = "%b %Y"

        else:
            df = stock.history(period="7d")
            date_format = "%d %b"

        # ✅ SAFETY CHECK
        if df is None or df.empty or len(df) < 2:
            return render(request, "index.html", context)

        # ===== CORE VALUES =====
        price = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        volume = df['Volume'].iloc[-1]
        trend = "UP" if price > prev else "DOWN"

        # ===== TABLE LOGIC =====
        if range_val == "1d":
            df_table = df.tail(12)

        elif range_val == "7d":
            df_table = df.resample('1D').agg({
                'Open': 'first',
                'Close': 'last',
                'High': 'max',
                'Low': 'min'
            }).dropna()

        elif range_val == "1mo":
            df_table = df.tail(20)

        elif range_val == "1y":
            df = df.copy()
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()

            df['Month'] = df.index.to_period('M')

            df_table = df.groupby('Month').agg({
                'Open': 'first',
                'Close': 'last',
                'High': 'max',
                'Low': 'min'
            }).dropna()

            df_table.index = df_table.index.to_timestamp()

        else:
            df_table = df.tail(10)

        # ===== DATA BUILD =====
        data = []
        candles = []

        for i in range(len(df_table)):
            d = df_table.index[i]

            open_p = round(df_table['Open'].iloc[i], 2)
            high_p = round(df_table['High'].iloc[i], 2)
            low_p = round(df_table['Low'].iloc[i], 2)
            close_p = round(df_table['Close'].iloc[i], 2)

            data.append({
                "date": d.strftime(date_format),
                "open": open_p,
                "close": close_p,
                "high": high_p,
                "low": low_p,
            })

            # ✅ FIXED (use df_table index, not df)
            candles.append({
                "x": d.strftime("%Y-%m-%d %H:%M:%S"),
                "y": [open_p, high_p, low_p, close_p]
            })

        labels = [d["date"] for d in data]
        prices = [d["close"] for d in data]

        # ===== UPDATE CONTEXT =====
        context.update({
            "price": round(price, 2),
            "volume": int(volume),
            "trend": trend,
            "data": data,
            "labels": json.dumps(labels),
            "prices": json.dumps(prices),
            "candles": json.dumps(candles),
        })

    except Exception as e:
        print("ERROR:", e)

    return render(request, "index.html", context)
    symbol = request.GET.get('stock') or request.POST.get('stock')
    range_val = request.POST.get('range', '1mo')

    context = {
        "symbol": symbol,
        "range": range
    }


    if request.method == "POST":
        symbol = request.POST.get("stock")
        range_val = request.POST.get("range")

    # ✅ ALWAYS define context first (important fix)
    context = {
        "price": 0,
        "volume": 0,
        "trend": "DOWN",
        "data": [],
        "labels": "[]",
        "prices": "[]",
        "candles": "[]",
        "range": range_val
    }

    try:
        stock = yf.Ticker(symbol)

        # 🔥 Time logic
        if range_val == "1d":
            df = stock.history(period="1d", interval="5m")
            date_format = "%H:%M"
        elif range_val == "7d":
            df = stock.history(period="7d", interval="1h")
            date_format = "%d %b %H:%M"
        elif range_val == "1mo":
            df = stock.history(period="1mo", interval="1d")
            date_format = "%d %b"
        elif range_val == "1y":
            df = stock.history(period="1y", interval="1wk")
            date_format = "%b %Y"
        else:
            df = stock.history(period="7d")
            date_format = "%d %b"

        # ✅ Safety check
        if df is None or df.empty or len(df) < 2:
            return render(request, "index.html", context)

        # --- VALUES ---
        price = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        volume = df['Volume'].iloc[-1]
        trend = "UP" if price > prev else "DOWN"

        # -------- SMART TABLE LOGIC --------

        if range_val == "1d":
            df_table = df.tail(12)   # last few hours
            date_format = "%H:%M"

        elif range_val == "7d":
            df_table = df.resample('1D').agg({
                'Open': 'first',
                'Close': 'last',
                'High': 'max',
                'Low': 'min'
            }).dropna()
            date_format = "%d %b"

        elif range_val == "1mo":
            df_table = df.tail(20)   # last 20 days
            date_format = "%d %b"

        elif range_val == "1y":
            # ✅ Ensure datetime + sorted
            df = df.copy()
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()

            # ✅ Convert to month column
            df['Month'] = df.index.to_period('M')

            df_table = df.groupby('Month').agg({
                'Open': 'first',
                'Close': 'last',
                'High': 'max',
                'Low': 'min'
            }).dropna()

            # Convert back to timestamp
            df_table.index = df_table.index.to_timestamp()

            date_format = "%b %Y"

        else:
            df_table = df.tail(10)
            date_format = "%d %b"
        

        data = []
        candles = []

        for i in range(len(df_table)):
            d = df_table.index[i]

            data.append({
                "date": d.strftime(date_format),
                "open": round(df_table['Open'].iloc[i], 2),
                "close": round(df_table['Close'].iloc[i], 2),
                "high": round(df_table['High'].iloc[i], 2),
                "low": round(df_table['Low'].iloc[i], 2),
            })

            candles.append({
                "x": df.index[i].strftime("%Y-%m-%d %H:%M:%S"),
                "y": [
                    round(df_table['Open'].iloc[i], 2),
                    round(df_table['High'].iloc[i], 2),
                    round(df_table['Low'].iloc[i], 2),
                    round(df_table['Close'].iloc[i], 2)
                ]
            })

        labels = [d["date"] for d in data]
        prices = [d["close"] for d in data]


        # ✅ UPDATE context (safe)
        context.update({
            "price": round(price, 2),
            "volume": volume,
            "trend": trend,
            "data": data,
            "labels": json.dumps(labels),
            "prices": json.dumps(prices),
            "candles": json.dumps(candles),
            "symbol": symbol
        })

    except Exception as e:
        print("ERROR:", e)

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
        "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
        "SBIN.NS","ITC.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS",
        "BHARTIARTL.NS","ASIANPAINT.NS","MARUTI.NS","TITAN.NS","ULTRACEMCO.NS",
        "AAPL","MSFT","GOOGL","AMZN","TSLA","META","NFLX","NVDA",
        "BTC-USD","ETH-USD"
    ]

    results = []

    for symbol in stocks_list:
        try:
            stock = yf.Ticker(symbol)
            data = stock.history(period="5d")

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


