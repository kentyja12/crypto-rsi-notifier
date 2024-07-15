import yfinance as yf
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import json
import warnings
from bs4 import BeautifulSoup
import requests
from lxml import html

# Disabled Warning
warnings.simplefilter('ignore')

# 設定をJSONファイルから読み込み
with open('config/.stock_config.json', 'r') as file:
    config = json.load(file)

# 設定
STOCK_TICKER = config['stock_ticker']
RSI_THRESHOLD = config['rsi_threshold']
EMAIL_ADDRESS = config['email_address']
EMAIL_PASSWORD = config['email_password']
TO_EMAIL_ADDRESS = config['to_email_address']
SMTP_SERVER = config['smtp_server']
SMTP_PORT = config['smtp_port']

# ログ設定
logging.basicConfig(filename='log/stock_rsi_alert.log', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

def get_stock_name(ticker):
    url = f"https://www.cnbc.com/quotes/{ticker}"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    lxml_data = html.fromstring(str(soup))
    name_tag  = lxml_data.xpath('//*[@id="quote-page-strip"]/div[1]/h1/span[1]')
    return name_tag[0].text

def calculate_rsi(data, window=14):
    delta = data['Close'].diff(1)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi

def get_stock_rsi(ticker, period, interval):
    stock_data = yf.download(ticker, period=period, interval=interval)
    stock_data.dropna(inplace=True)
    stock_data['RSI'] = calculate_rsi(stock_data)
    return stock_data

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

def save_rsi_data(data, filename):
    data['Date'] = data.index
    data = data[['Date', 'Close', 'RSI']]
    data.to_csv(filename, index=False)

def main():
    try:
        logging.info("Script started.")
        stock_name = get_stock_name(STOCK_TICKER)

        # 月足
        monthly_data = get_stock_rsi(STOCK_TICKER, period='5y', interval='1mo')
        save_rsi_data(monthly_data, 'monthly_rsi_data.csv')
        logging.info("Monthly RSI data saved.")
        monthly_alert = check_rsi_threshold(monthly_data, RSI_THRESHOLD)
        monthly_rsi = monthly_data["RSI"].iloc[-1]

        # 週足
        weekly_data = get_stock_rsi(STOCK_TICKER, period='5y', interval='1wk')
        save_rsi_data(weekly_data, 'weekly_rsi_data.csv')
        logging.info("Weekly RSI data saved.")
        weekly_alert = check_rsi_threshold(weekly_data, RSI_THRESHOLD)
        weekly_rsi = weekly_data["RSI"].iloc[-1]

        # 日足
        daily_data = get_stock_rsi(STOCK_TICKER, period='1y', interval='1d')
        save_rsi_data(daily_data, 'daily_rsi_data.csv')
        logging.info("Daily RSI data saved.")
        daily_alert = check_rsi_threshold(daily_data, RSI_THRESHOLD)
        daily_rsi = daily_data["RSI"].iloc[-1]

        # メール本文作成
        body = f"{stock_name} ({STOCK_TICKER}) RSI Alert:\n\n"
        if monthly_alert:
            body += f"Monthly RSI has fallen below {RSI_THRESHOLD}. Current Monthly RSI: {monthly_rsi}\n"
        if weekly_alert:
            body += f"Weekly RSI has fallen below {RSI_THRESHOLD}. Current Weekly RSI: {weekly_rsi}\n"
        if daily_alert:
            body += f"Daily RSI has fallen below {RSI_THRESHOLD}. Current Daily RSI: {daily_rsi}\n"

        if monthly_alert or weekly_alert or daily_alert:
            send_email(f'{stock_name} RSI Alert', body)
            logging.info("Email sent successfully.")
        else:
            logging.info("No RSI threshold breaches.")

    except Exception as e:
        logging.error(f"Error occurred: {e}")

if __name__ == '__main__':
    main()
