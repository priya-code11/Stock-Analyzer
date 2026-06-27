import os
import json
import time
import urllib.parse
import urllib.request
import pandas as pd
from decimal import Decimal

from django.db import transaction, connections
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

# Decoupled Imports to prevent Circular Dependency loops
from .utils import get_historical_candles_helper, US_HEAVYWEIGHTS
from .agent import execute_financial_agent
from .context_processors import notification_context
from .models import Notification, PriceAlert, Watchlist


def check_alerts():
    print("CHECK_ALERTS CALLED VIA INDEPENDENT YAHOO FINANCE BACKEND")
    
    with transaction.atomic():
        alerts = PriceAlert.objects.filter(is_active=True, triggered=False)
        print("TOTAL ALERTS:", alerts.count())

        for alert in alerts:
            alert_condition = str(alert.condition).strip().lower()
            ticker = alert.stock_symbol.strip().upper()
            
            if "." in ticker:
                ticker = ticker.split(".")[0]
            
            print("Checking:", ticker, alert_condition, alert.target_price)
            try:
                # Twelve Data fallback completely removed. Everything routes through local Yahoo endpoint
                encoded_sym = urllib.parse.quote(f"{ticker}.NS")
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_sym}?range=1d&interval=1m"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                
                with urllib.request.urlopen(req, timeout=3) as r:
                    j_data = json.loads(r.read().decode('utf-8'))
                
                c_root = j_data.get("chart", {}).get("result", [None])[0]
                if c_root:
                    curr_close = c_root.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                    valid_closes = [c for c in curr_close if c is not None]
                    price = Decimal(str(valid_closes[-1])) if valid_closes else None
                else:
                    price = None

                if price is None:
                    print(f"NO DATA OR API LIMIT HIT FOR {ticker}")
                    continue

                print("CURRENT PRICE:", price)
                target = Decimal(str(alert.target_price))

                trigger = False
                if alert_condition == "above" and price >= target:
                    trigger = True
                elif alert_condition == "below" and price <= target:
                    trigger = True

                print("TRIGGER =", trigger)

                if trigger:
                    notification = Notification.objects.create(
                        user=alert.user,
                        message=f"{ticker} reached ₹{price:.2f}"
                    )
                    print("ALERT TRIGGERED. USER ID =", alert.user.id)

                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f"notif_{alert.user.id}",
                        {
                            "type": "send_notification",
                            "message": notification.message,
                            "unread_count": Notification.objects.filter(
                                user=alert.user, is_read=False
                            ).count()
                        }
                    )

                    alert.triggered = True
                    alert.is_active = False
                    alert.save()

            except Exception as e:
                print(f"ERROR IN CHECK_ALERTS FOR {ticker}:", e)
                
    for conn in connections.all():
        conn.close()


def format_volume(volume):
    try:
        val = float(volume)
        if val >= 1_000_000_000:
            return f"{val / 1_000_000_000:.2f}B"
        elif val >= 1_000_000:
            return f"{val / 1_000_000:.2f}M"
        elif val >= 1_000:
            return f"{val / 1_000:.2f}K"
        return str(int(val))
    except (ValueError, TypeError):
        return "0"


def live_stock_data(request):
    symbol = request.GET.get("symbol", "TATASTEEL").strip().upper()
    range_val = request.GET.get("range", "1D")
    
    candles_raw, latest_price = get_historical_candles_helper(symbol, range_val)
    formatted_candles = [[c[0], c[1], c[2], c[3], c[4]] for c in candles_raw]

    return JsonResponse({
        "candles": formatted_candles,
        "price": latest_price
    })


def index(request):
    symbol = (
        request.GET.get("stock") or 
        request.POST.get("stock") or 
        request.session.get("dashboard_stock", "RELIANCE") # Swapped default base stock fallback to RELIANCE
    )
    
    range_val = request.POST.get("range") or request.session.get("dashboard_range", "1D")
    
    symbol = symbol.strip().upper()
    request.session["dashboard_stock"] = symbol
    request.session["dashboard_range"] = range_val

    pure_symbol = symbol.split(".")[0]
    trend = "UP"

    candles_raw, latest_price = get_historical_candles_helper(pure_symbol, range_val)
    
    candles = []
    table_data = []
    
    for c in candles_raw:
        candles.append([c[0], c[1], c[2], c[3], c[4]])
        table_data.append({
            "date": c[5], "open": f"{c[1]:.2f}", "close": f"{c[4]:.2f}",
            "high": f"{c[2]:.2f}", "low": f"{c[3]:.2f}"
        })
        
    if candles and len(candles) >= 2 and candles[-1][4] < candles[-2][4]:
        trend = "DOWN"

    context = {
        "symbol": pure_symbol.upper(),
        "range": range_val,
        "price": latest_price,
        "candles": candles,
        "data": table_data,
        "trend": trend,
        "formatted_volume": "N/A"
    }
    return render(request, "index.html", context)


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
    reason = None
    
    symbol = request.POST.get("stock") or request.GET.get("stock") or "RELIANCE"
    symbol = symbol.strip().upper()
    pure_symbol = symbol.split(".")[0]

    try:
        candles_raw, latest_price = get_historical_candles_helper(pure_symbol, "1Y")

        if not candles_raw or len(candles_raw) < 50:
            error = f"Asset '{pure_symbol}' lacks sufficient data metrics to perform calculations."
            return render(request, "prediction.html", {"symbol": pure_symbol, "name": pure_symbol, "error": error})

        df = pd.DataFrame(candles_raw, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Date'])
        
        df["MA20"] = df["Close"].rolling(window=20).mean()
        df["MA50"] = df["Close"].rolling(window=50).mean()
        df["RSI"] = calculate_rsi(df)

        latest = df.iloc[-1]

        price = float(latest["Close"])
        ma20 = float(latest["MA20"])
        ma50 = float(latest["MA50"])
        rsi = float(latest["RSI"]) if not pd.isna(latest["RSI"]) else 50.0

        stock_data = {
            "price": round(price, 2),
            "ma20": round(ma20, 2),
            "ma50": round(ma50, 2),
            "rsi": round(rsi, 2),
            "symbol": pure_symbol,
        }

        distance = abs(price - ma20) / ma20 * 100
        conf = min(95, round(60 + distance * 2))

        if price > ma20 and ma20 > ma50 and rsi < 70:
            result = "BUY"
            confidence = f"{conf}%"
            reason = "Price is establishing structural support above moving averages. Momentum profiles are bullish."
        elif price < ma20 and ma20 < ma50 and rsi > 30:
            result = "SELL"
            confidence = f"{conf}%"
            reason = "Asset broke structural floor support. Bear vectors have baseline volume distribution control."
        else:
            result = "HOLD"
            confidence = f"{max(55, conf - 15)}%"
            reason = "Oscillator indicators are tracking in mixed consolidation bands. Await clean accumulation confirmation."

    except Exception as e:
        error = f"Telemetry metric intercept execution fault: {str(e)}"
        stock_data = None

    return render(
        request, "prediction.html",
        {
            "symbol": pure_symbol,
            "name": pure_symbol,
            "prediction": result,
            "confidence": confidence,
            "stock": stock_data,
            "reason": reason,
            "error": error,
        }
    )


def market_trends(request):
    # Removed US stocks and Cryptocurrencies completely (AAPL, NVDA, BTC, etc.)
    stocks_list = [
        "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
        "SBIN", "ITC", "LT", "AXISBANK", "KOTAKBANK"
    ]

    results = []
    for symbol in stocks_list:
        try:
            pure_symbol = symbol.split(".")[0]
            candles_raw, _ = get_historical_candles_helper(pure_symbol, "1M")

            if not candles_raw or len(candles_raw) < 2:
                continue

            price = float(candles_raw[-1][4])
            prev_price = float(candles_raw[-2][4])

            change = price - prev_price
            trend = "UP" if change > 0 else "DOWN"

            results.append({
                "symbol": pure_symbol,
                "price": round(price, 2),
                "change": round(change, 2),
                "trend": trend
            })
        except Exception as e:
            print(f"Error processing trends matrix for {symbol}: {e}")
            continue

    return render(request, "market_trends.html", {"stocks": results})


def ticker_autocomplete(request):
    q = request.GET.get('q', '').strip().upper()
    if not q:
        return JsonResponse({"suggestions": []})
        
    top_indian_stocks = [
        {"ticker": "ADANIENT", "name": "Adani Enterprises Ltd."},
        {"ticker": "ADANIPORTS", "name": "Adani Ports & SEZ Ltd."},
        {"ticker": "AMBUJACEM", "name": "Ambuja Cements Ltd."},
        {"ticker": "APOLLOHOSP", "name": "Apollo Hospitals Enterprise Ltd."},
        {"ticker": "ASIANPAINT", "name": "Asian Paints Ltd."},
        {"ticker": "AXISBANK", "name": "Axis Bank Ltd."},
        {"ticker": "BAJAJ-AUTO", "name": "Bajaj Auto Ltd."},
        {"ticker": "BAJFINANCE", "name": "Bajaj Finance Ltd."},
        {"ticker": "BAJAJFINSV", "name": "Bajaj Finserv Ltd."},
        {"ticker": "BHARTIARTL", "name": "Bharti Airtel Ltd."},
        {"ticker": "BPCL", "name": "Bharat Petroleum Corporation Ltd."},
        {"ticker": "BRITANNIA", "name": "Britannia Industries Ltd."},
        {"ticker": "CIPLA", "name": "Cipla Ltd."},
        {"ticker": "COALINDIA", "name": "Coal India Ltd."},
        {"ticker": "DIVISLAB", "name": "Divi's Laboratories Ltd."},
        {"ticker": "DRREDDY", "name": "Dr. Reddy's Laboratories Ltd."},
        {"ticker": "EICHERMOT", "name": "Eicher Motors Ltd."},
        {"ticker": "GRASIM", "name": "Grasim Industries Ltd."},
        {"ticker": "HCLTECH", "name": "HCL Technologies Ltd."},
        {"ticker": "HDFCBANK", "name": "HDFC Bank Ltd."},
        {"ticker": "HDFCLIFE", "name": "HDFC Life Insurance Company Ltd."},
        {"ticker": "HEROMOTOCO", "name": "Hero MotoCorp Ltd."},
        {"ticker": "HINDALCO", "name": "Hindalco Industries Ltd."},
        {"ticker": "HINDUNILVR", "name": "Hindustan Unilever Ltd."},
        {"ticker": "ICICIBANK", "name": "ICICI Bank Ltd."},
        {"ticker": "ITC", "name": "ITC Ltd."},
        {"ticker": "INDUSINDBK", "name": "IndusInd Bank Ltd."},
        {"ticker": "INFY", "name": "Infosys Ltd."},
        {"ticker": "JSWSTEEL", "name": "JSW Steel Ltd."},
        {"ticker": "KOTAKBANK", "name": "Kotak Mahindra Bank Ltd."},
        {"ticker": "LT", "name": "Larsen & Toubro Ltd."},
        {"ticker": "LTIM", "name": "LTIMindtree Ltd."},
        {"ticker": "M&M", "name": "Mahindra & Mahindra Ltd."},
        {"ticker": "MARUTI", "name": "Maruti Suzuki India Ltd."},
        {"ticker": "NTPC", "name": "NTPC Ltd."},
        {"ticker": "NESTLEIND", "name": "Nestle India Ltd."},
        {"ticker": "ONGC", "name": "Oil & Natural Gas Corporation Ltd."},
        {"ticker": "POWERGRID", "name": "Power Grid Corporation of India Ltd."},
        {"ticker": "RELIANCE", "name": "Reliance Industries Ltd."},
        {"ticker": "SBILIFE", "name": "SBI Life Insurance Company Ltd."},
        {"ticker": "SBIN", "name": "State Bank of India"},
        {"ticker": "SUNPHARMA", "name": "Sun Pharmaceutical Industries Ltd."},
        {"ticker": "TCS", "name": "Tata Consultancy Services Ltd."},
        {"ticker": "TATACONSUM", "name": "Tata Consumer Products Ltd."},
        {"ticker": "TATAMOTORS", "name": "Tata Motors Ltd."},
        {"ticker": "TATASTEEL", "name": "Tata Steel Ltd."},
        {"ticker": "TECHM", "name": "Tech Mahindra Ltd."},
        {"ticker": "TITAN", "name": "Titan Company Ltd."},
        {"ticker": "ULTRACEMCO", "name": "UltraTech Cement Ltd."},
        {"ticker": "WIPRO", "name": "Wipro Ltd."},
    ]

    results = [
        stock for stock in top_indian_stocks 
        if stock["ticker"].startswith(q) or q in stock["name"].upper()
    ]

    return JsonResponse({"suggestions": results[:6]})


def about(request):
    return render(request, 'about.html')


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})


@login_required(login_url='login')
def add_watchlist(request):
    if request.method == "POST":
        symbol = request.POST.get("symbol")
        if symbol:
            symbol = symbol.strip().upper().split(".")[0]
            exists = Watchlist.objects.filter(user=request.user, stock_symbol=symbol).exists()
            if not exists:
                Watchlist.objects.create(user=request.user, stock_symbol=symbol)
    return redirect('/')


@login_required(login_url='login')
def watchlist(request):
    stocks = Watchlist.objects.filter(user=request.user)
    notifications_list = Notification.objects.filter(user=request.user).order_by("-created_at")[:20]
    return render(request, "watchlist.html", {"stocks": stocks, "notifications": notifications_list})


def logout_user(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('/')


@login_required
def delete_account(request):
    if request.method == "POST":
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "Account deleted successfully.")
        return redirect('/')
    return render(request, "delete_account.html")


@login_required
def remove_watchlist(request, stock_id):
    if request.method == "POST":
        stock = get_object_or_404(Watchlist, id=stock_id, user=request.user)
        stock.delete()
    return redirect('watchlist')


@login_required
def create_alert(request):
    if request.method == "POST":
        symbol = request.POST.get("symbol")
        target_price = request.POST.get("target_price")
        condition = request.POST.get("condition")

        if symbol and target_price and condition:
            symbol = symbol.strip().upper().split(".")[0]
            PriceAlert.objects.get_or_create(
                user=request.user,
                stock_symbol=symbol,
                target_price=target_price,
                condition=condition
            )
    return redirect("watchlist")


@login_required
def notifications(request):
    data = Notification.objects.filter(user=request.user).order_by("-created_at")
    return JsonResponse({"notifications": list(data.values("message", "created_at"))})


def get_notifications(request):
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({"unread_count": 0, "notifications": []})

    notes = Notification.objects.filter(user=request.user).order_by("-created_at")
    return JsonResponse({
        "unread_count": notes.filter(is_read=False).count(),
        "notifications": list(notes.values("id", "message", "is_read"))
    })


@login_required
def mark_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({"success": True})


def home(request):
    if hasattr(request, 'user') and request.user.is_authenticated:
        stocks = Watchlist.objects.filter(user=request.user)
        notifications_list = Notification.objects.filter(user=request.user).order_by("-created_at")[:20]
    else:
        stocks = []
        notifications_list = []

    return render(
        request, "index.html",
        {
            "stocks": stocks,
            "notifications": notifications_list,
            "symbol": "RELIANCE",
            "range": "1W",
            "price": 0.00,
            "volume": 0,
            "formatted_volume": "0",
            "trend": "DOWN",
            "data": [],
            "candles": "[]"
        }
    )


@login_required
def delete_notification(request, notif_id):
    try:
        notification = Notification.objects.get(id=notif_id, user=request.user)
        notification.delete()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)


def notification_poll(request):
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({"message": "", "unread_count": 0})

    context = notification_context(request)
    notifs = context.get("notifications", [])
    
    latest_message = ""
    if notifs:
        latest_message = notifs[0].message
        
    return JsonResponse({
        "message": latest_message,
        "unread_count": context.get("unread_count", 0)
    })


def check_live_notifications(request):
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({"unread_count": 0, "notifications": []})

    current_time = time.time()
    last_check = 0
    
    if hasattr(request, "session") and request.session is not None:
        last_check = request.session.get('last_alert_check_timestamp', 0)
    
    if current_time - last_check > 60:
        try:
            check_alerts()
            if hasattr(request, "session") and request.session is not None:
                request.session['last_alert_check_timestamp'] = current_time
        except Exception as e:
            print("Background alert processing exception:", e)

    context = notification_context(request)
    notifs = context.get("notifications", [])
    
    serialized_notifications = [{"id": n.id, "message": n.message} for n in notifs]
        
    return JsonResponse({
        "unread_count": context.get("unread_count", 0),
        "notifications": serialized_notifications
    })


@login_required(login_url='login')
def ai_agent_copilot(request):
    response_text = None
    query_string = ""
    
    print(f"--- AI COPILOT VIEW HIT --- Method: {request.method}")
    
    if request.method == "POST":
        query_string = request.POST.get("user_query", "").strip()
        print(f"User Query received: {query_string}")
        if query_string:
            try:
                response_text = execute_financial_agent(query_string)
                print(f"Agent executed successfully. Response length: {len(str(response_text))}")
            except Exception as e:
                print(f"CRITICAL ERROR IN AGENT EXECUTION: {e}")
                response_text = f"🚨 **Agent Core Failure**: Unable to execute sequence. Details: {str(e)}"
    else:
        response_text = "System online. Waiting for user payload query..."

    return render(request, "ai_agent.html", {
        "user_query": query_string,
        "agent_response": response_text
    })