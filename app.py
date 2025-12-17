import streamlit as st
import pandas as pd
from finvizfinance.screener.overview import Overview
import yfinance as yf
from textblob import TextBlob
import time
import subprocess
import sys

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Deep Value Analyzer", layout="wide")

# Fix for TextBlob
@st.cache_resource
def download_textblob_corpora():
    try:
        subprocess.check_call([sys.executable, "-m", "textblob.download_corpora"])
    except Exception as e:
        pass 

download_textblob_corpora()

# --- 2. SIDEBAR ---
st.sidebar.title("🎛️ Settings")
st.sidebar.write("Start with 'Any'. If you see results, then add filters.")

mc_option = st.sidebar.selectbox("Market Cap", ["Any", "Small ($300mln to $2bln)", "Micro ($50mln to $300mln)"], index=0)
pe_option = st.sidebar.selectbox("P/E Ratio", ["Any", "Under 15", "Under 20", "Under 30"], index=0)
pb_option = st.sidebar.selectbox("Price/Book", ["Any", "Under 1", "Under 2", "Under 3"], index=0)
debt_option = st.sidebar.selectbox("Debt/Equity", ["Any", "Under 0.5", "Under 1"], index=0)

# --- 3. MAIN LOGIC ---
def run_fast_scan():
    status = st.empty()
    status.info("1/3: Connecting to Finviz...")
    
    filters_dict = {}
    if mc_option != "Any": filters_dict['Market Cap.'] = mc_option
    if pe_option != "Any": filters_dict['P/E'] = pe_option
    if pb_option != "Any": filters_dict['P/B'] = pb_option
    if debt_option != "Any": filters_dict['Debt/Equity'] = debt_option

    foverview = Overview()
    
    # --- THE FIX IS HERE ---
    # If filters are empty (all "Any"), we force 'Top Gainers' to ensure we get data.
    if not filters_dict:
        foverview.set_filter(signal='Top Gainers')
    else:
        foverview.set_filter(filters_dict=filters_dict)
        
    try:
        df_results = foverview.screener_view()
        if df_results.empty:
            status.error("No stocks found. Try looser filters (e.g., P/B 'Under 3').")
            return None
    except Exception as e:
        status.error(f"Finviz Connection Error: {e}")
        return None

    status.info(f"2/3: Found {len(df_results)} stocks. Checking News on top 3...")
    
    # --- LOOP FIX IS HERE ---
    # We only take the top 3 stocks to prevent the app from freezing
    df_scan = df_results.head(3)
    results_data = []
    
    progress = st.progress(0)
    
    for i, (index, row) in enumerate(df_scan.iterrows()):
        symbol = row['Ticker']
        progress.progress((i + 1) / len(df_scan))
        
        try:
            # Fetch news
            stock = yf.Ticker(symbol)
            news = stock.news
            
            sentiment_score = 0
            if news:
                title = news[0].get('title', '')
                sentiment_score = TextBlob(title).sentiment.polarity
            
            results_data.append({
                "Ticker": symbol,
                "Price": row['Price'],
                "P/E": row['P/E'],
                "P/B": row['P/B'],
                "Sentiment": round(sentiment_score, 2)
            })
        except Exception:
            pass # Skip errors
            
        time.sleep(0.1) 

    status.success("3/3: Done!")
    progress.empty()
    return pd.DataFrame(results_data)

# --- 4. UI ---
st.title("🚀 Fast Value Finder")

if st.button("Run Scan"):
    df = run_fast_scan()
    if df is not None:
        st.dataframe(df, use_container_width=True)
