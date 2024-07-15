import yfinance as yf
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import json
import warnings

# Disabled Warning
warnings.simplefilter('ignore')

# 設定をJSONファイルから読み込み
with open('config/.crypto_config.json', 'r') as file:
    config = json.load(file)

# 設定
BTC_TICKER = config['btc_ticker']
RSI_THRESHOLD = config['rsi_threshold']
EMAIL_ADDRESS = config['email_address']
EMAIL_PASSWORD = config['email_password'] 
TO_EMAIL_ADDRESS = config['to_email_address']
SMTP_SERVER = config['smtp_server']
SMTP_PORT = config['smtp_port']

# ログ設定
logging.basicConfig(filename='log/btc_rsi_alert.log', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

def calculate_rsi(data, window=14):
    delta = data['Close'].diff(1)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi

def get_btc_monthly_rsi(ticker):
    # ビットコインのデータを取得
    btc_data = yf.download(ticker, period='5y', interval='1mo')
    btc_data.dropna(inplace=True)
    
    # RSIを計算
    btc_data['RSI'] = calculate_rsi(btc_data)
    
    return btc_data

def get_exchange_rate():
    # 通貨ペアの定義
    currency_pair = 'USDJPY=X'
    # Tickerオブジェクトの作成
    ticker = yf.Ticker(currency_pair)
    # 最新データの取得
    data = ticker.history(period='1d')

    if data["Open"][0]:
        return data["Open"][0]
    else:
        logging.error("Failed to retrieve exchange rate.")
        return None

def check_rsi_threshold(data, threshold):
    latest_rsi = data['RSI'].iloc[-1]
    return latest_rsi < threshold

def send_email(subject, body):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = TO_EMAIL_ADDRESS
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))
    
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, TO_EMAIL_ADDRESS, msg.as_string())

def save_rsi_data(data, usd_to_jpy, filename='btc_rsi_data.csv'):
    data['Date'] = data.index
    data = data[['Date', 'Close', 'RSI']]
    
    # JPYへの変換
    data['Close_JPY'] = data['Close'] * usd_to_jpy
    
    data.to_csv(filename, index=False)

def main():
    try:
        logging.info("Script started.")
        btc_data = get_btc_monthly_rsi(BTC_TICKER)
        
        usd_to_jpy = get_exchange_rate()
        if usd_to_jpy is None:
            logging.error("Could not get exchange rate. Exiting.")
            return
        
        save_rsi_data(btc_data, usd_to_jpy)
        logging.info("RSI data saved.")
        
        if check_rsi_threshold(btc_data, RSI_THRESHOLD):
            subject = 'Bitcoin RSI Alert'
            body = f'The monthly RSI of Bitcoin has fallen below {RSI_THRESHOLD}. Current RSI: {btc_data["RSI"].iloc[-1]}'
            send_email(subject, body)
            logging.info("Email sent successfully.")
        else:
            logging.info("RSI threshold not met.")
    except Exception as e:
        logging.error(f"Error occurred: {e}")

if __name__ == '__main__':
    main()
