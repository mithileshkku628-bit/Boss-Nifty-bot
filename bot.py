from SmartApi import SmartConnect
import time, datetime, requests, pyotp, json, os

# ================= LOGIN =================
API_KEY = "I2Ai40Jo"
CLIENT_ID = "M187274"
PASSWORD = "3371"
TOTP_SECRET = "UNDPET7Q5TI67WL34G34FR76DA"

totp = pyotp.TOTP(TOTP_SECRET).now()
obj = SmartConnect(api_key=API_KEY)
session = obj.generateSession(CLIENT_ID, PASSWORD, totp)

print("FINAL STRATEGY BOT 🚀")

# ================= TELEGRAM =================
BOT_TOKEN = "8709432394:AAFRmqz1sCDBmAW1ybAeITYo-NZZyMFbr_w"
CHAT_ID = "7443689154"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# ================= MEMORY =================
STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"stoch_count": 0, "last_signal": "", "last_reset_date": ""}

def save_state(state):
    json.dump(state, open(STATE_FILE, "w"))

state = load_state()

# ================= RESET DAILY =================
today = datetime.date.today().isoformat()
if state["last_reset_date"] != today:
    state["stoch_count"] = 0
    state["last_reset_date"] = today
    save_state(state)

# ================= INSTRUMENT =================
def get_instruments():
    url = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"
    return requests.get(url).json()

instruments = get_instruments()

# ================= ATM OPTION =================
def get_atm_option(ltp):
    atm = round(ltp / 50) * 50
    for ins in instruments:
        if ins['name'] == "NIFTY" and str(atm) in ins['symbol'] and ins['symbol'].endswith("CE"):
            return ins['symbol'], ins['token']
    return None, None

# ================= DATA =================
def get_data(token):
    params = {
        "exchange": "NFO",
        "symboltoken": token,
        "interval": "FIVE_MINUTE",
        "fromdate": datetime.datetime.now().strftime("%Y-%m-%d") + " 09:15",
        "todate": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    res = obj.getCandleData(params)
    df = pd.DataFrame(res['data'], columns=['time','open','high','low','close','volume'])

    df['close'] = df['close'].astype(float)

    # 🔥 OI proxy
    df['oi'] = df['volume']
    df['oi_sma'] = df['oi'].rolling(20).mean()

    return df

# ================= INDICATORS =================
def apply_indicators(df):
    df['rsi'] = ta.rsi(df['close'], 14)

    stoch = ta.stochrsi(df['close'])
    df['stoch'] = stoch['STOCHRSIk_14_14_3_3']

    macd = ta.macd(df['close'])
    df['macd'] = macd['MACD_12_26_9']
    df['signal'] = macd['MACDs_12_26_9']

    return df

# ================= STRATEGY =================
def check_entry(df):
    last = df.iloc[-2]
    prev = df.iloc[-3]

    # Stoch second cross logic
    if last['stoch'] > 80 and prev['stoch'] <= 80:
        state["stoch_count"] += 1
        save_state(state)

    cond1 = last['rsi'] > 50
    cond2 = last['oi_sma'] > last['oi']
    cond3 = last['macd'] > last['signal']
    cond4 = state["stoch_count"] >= 2

    if cond1 and cond2 and cond3 and cond4:
        return True, last

    return False, None

# ================= WAIT CANDLE CLOSE =================
def wait_candle():
    while True:
        now = datetime.datetime.now()
        if now.minute % 5 == 0 and now.second < 2:
            return
        time.sleep(1)

# ================= MAIN =================
while True:
    try:
        now = datetime.datetime.now()

        if now.time() < datetime.time(9,30) or now.time() > datetime.time(14,30):
            time.sleep(30)
            continue

        wait_candle()

        spot = obj.ltpData("NSE", "NIFTY 50", "99926000")['data']['ltp']

        symbol, token = get_atm_option(spot)

        if not symbol:
            continue

        df = apply_indicators(get_data(token))
        signal, candle = check_entry(df)

        if signal:
            current_time = candle['time']

            if state["last_signal"] == current_time:
                continue

            state["last_signal"] = current_time
            save_state(state)

            entry = candle['high'] + 1
            sl = candle['low']
            target = entry + 25

            msg = f"""
🚀 YOUR STRATEGY SIGNAL

Symbol: {symbol}
Entry: {entry}
SL: {sl}
Target: {target}
Time: {current_time}
"""

            print(msg)
            send_telegram(msg)

        time.sleep(2)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
