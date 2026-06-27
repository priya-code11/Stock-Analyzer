# Home/utils.py
import json
import datetime
import urllib.parse
import urllib.request
import pytz


# Global list of US heavyweights to route to Twelve Data
US_HEAVYWEIGHTS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NFLX", "NVDA", "AMD", "INTC"]

def get_historical_candles_helper(symbol, range_val="1M"):
    """
    Unified fallback helper to securely route market streams without repeated code blocks.
    Returns a structured list of candle data points.
    """
    symbol = symbol.strip().upper()
    pure_symbol = symbol.split(".")[0]
    
    is_crypto = "/" in symbol or "-" in symbol
    is_indian = (pure_symbol not in US_HEAVYWEIGHTS) and (not is_crypto)
    
    candles = []
    latest_price = "0.00"
    
    if is_indian:
        query_symbol = f"{pure_symbol}.NS"
        indian_range_map = {
            "1D": ("1d", "5m"),
            "1W": ("7d", "30m"),
            "1M": ("1mo", "1d"),
            "1Y": ("1y", "1d"),
        }
        api_range, api_interval = indian_range_map.get(range_val, ("1mo", "1d"))
        try:
            encoded_sym = urllib.parse.quote(query_symbol)
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_sym}?range={api_range}&interval={api_interval}"
            
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                json_data = json.loads(response.read().decode('utf-8'))
                
            chart_root = json_data.get("chart", {}).get("result", [None])[0]
            if chart_root:
                timestamps = chart_root.get("timestamp", [])
                indicators = chart_root.get("indicators", {}).get("quote", [{}])[0]
                opens = indicators.get("open", [])
                highs = indicators.get("high", [])
                lows = indicators.get("low", [])
                closes = indicators.get("close", [])
                
                for i in range(len(timestamps)):
                    if (i >= len(opens) or opens[i] is None or 
                        highs[i] is None or lows[i] is None or closes[i] is None):
                        continue
                        
                    timestamp_ms = int(timestamps[i] * 1000)
                    utc_dt = datetime.datetime.fromtimestamp(timestamps[i], tz=datetime.timezone.utc)
                    ist_tz = pytz.timezone('Asia/Kolkata')
                    dt_object = utc_dt.astimezone(ist_tz)
                    
                    if range_val in ["1D", "1W"]:
                        dt_str = dt_object.strftime("%Y-%m-%d %H:%M")
                    else:
                        dt_str = dt_object.strftime("%Y-%m-%d")
                        
                    candles.append([
                        timestamp_ms,
                        round(float(opens[i]), 2),
                        round(float(highs[i]), 2),
                        round(float(lows[i]), 2),
                        round(float(closes[i]), 2),
                        dt_str
                    ])
                if candles:
                    latest_price = f"{candles[-1][4]:.2f}"
        except Exception as e:
            print(f"Helper pipeline Indian data parsing error for {pure_symbol}: {e}")
            
    return candles, latest_price