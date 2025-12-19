import streamlit as st
import pandas as pd
from finvizfinance.screener.valuation import Valuation
import yfinance as yf
from textblob import TextBlob
import time
import subprocess
import sys
import os
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Market Hunter & Analyst", layout="wide")

@st.cache_resource
def download_textblob_corpora():
    try:
        subprocess.check_call([sys.executable, "-m", "textblob.download_corpora"])
    except:
        pass 

# --- 2. HELPER FUNCTIONS ---

def load_portfolio():
    if os.path.exists('my_portfolio.csv'):
        return pd.read_csv('my_portfolio.csv')
    return pd.DataFrame(columns=['Ticker', 'Date Added', 'Price Added'])

def save_to_portfolio(ticker, current_price):
    df = load_portfolio()
    try: price_float = float(current_price)
    except: price_float = 0.0
    if ticker not in df['Ticker'].values:
        new_row = pd.DataFrame({'Ticker': [ticker], 'Date Added': [datetime.now().strftime("%Y-%m-%d")], 'Price Added': [price_float]})
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv('my_portfolio.csv', index=False)
        return True
    return False

def remove_from_portfolio(ticker):
    df = load_portfolio()
    df = df[df['Ticker'] != ticker]
    df.to_csv('my_portfolio.csv', index=False)

def get_performance_data(ticker):
    stock = yf.Ticker(ticker)
    cur, w, m = 0.0, 0.0, 0.0
    try:
        cur = stock.fast_info['last_price']
        hist = stock.history(period="2mo")
        if not hist.empty:
            w_idx = hist.index.get_indexer([datetime.now() - timedelta(days=7)], method='nearest')[0]
            m_idx = hist.index.get_indexer([datetime.now() - timedelta(days=30)], method='nearest')[0]
            pw, pm = hist['Close'].iloc[w_idx], hist['Close'].iloc[m_idx]
            if pw > 0: w = ((cur - pw) / pw) * 100
            if pm > 0: m = ((cur - pm) / pm) * 100
    except: pass
    return cur, w, m

# --- 3. APP NAVIGATION ---
st.sidebar.title("Navigation")
page = st.sidebar.r
