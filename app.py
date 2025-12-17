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
st.sidebar.write("Start with 'Any'. Then filter.")

mc_option = st.sidebar.selectbox("Market Cap", ["Any", "Small ($300mln to $2bln)", "Micro ($50mln to $300mln)"], index=0)
pe_option = st.sidebar.selectbox("P/E Ratio", ["Any", "Under 15", "Under 20", "Under 30"], index=0)
pb_option = st.sidebar.selectbox("Price/Book", ["Any", "Under 1", "Under 2", "Under 3"], index=0)
debt_option = st.sidebar.selectbox("Debt/Equity", ["Any", "Under 0.5", "Under 1"], index=0)

# --- 3. MAIN LOGIC ---
def run_robust_scan():
    status = st.empty()
    status.info("1/3: Connecting to Finviz...")
    
    filters_dict = {}
    if mc_option != "Any": filters_dict['Market Cap.'] = mc_option
    if pe_option != "Any": filters_dict['P/E'] = pe_option
    if pb_option != "Any": filters_dict['P/B'] = pb_option
    if debt_option != "Any": filters_dict['Debt/Equity'] = debt_option

    foverview = Overview()
    
    # Force Top Gainers if "Any" is selected to guarantee data
    if not filters_dict:
        foverview.set_filter(signal='Top Gainers')
    else:
        foverview.set_filter(filters_dict=filters_dict)
        
    try:
        df_results = foverview.screener_view()
        if df_results.empty:
            status.error("No stocks found. Try looser filters.")
            return None
    except Exception as e:
        status.error(f"Finviz Connection Error: {e}")
        return None

    status.info(f"2/3: Found {len(df_results)} stocks. Checking News on top 5...")
    
    # Limit to top 5
    df_scan = df_results.head(5)
    results_data = []
    
    progress = st.progress(0)
    
    for i, (index, row) in enumerate(df_scan.iterrows()):
        symbol = row['Ticker']
        progress.progress((i + 1) / len(df_scan))
        
        # Default sentiment is 0 ("N/A")
        sentiment_score = 0.0
        note = "N/A (News Error)"
        
        # Try to get news, but if it fails, WE KEEP GOING
        try:
            stock = yf.Ticker(symbol)
            news = stock.news
            if news:
                title = news[0].get('title', '')
                sentiment_score = TextBlob(title).sentiment.polarity
                note = "News Found"
            else:
                note = "No News"
        except Exception:
            note = "Connection Blocked"
            
        # --- THE FIX: We append OUTSIDE the try/except block ---
        # This ensures the stock shows up even if Yahoo blocks us
        results_data.append({
            "Ticker": symbol,
            "Price": row['Price'],
            "P/E": row['P/E'],
            "P/B": row['P/B'],
            "Sector": row['Sector'],
            "Sentiment": round(sentiment_score, 2),
            "Status": note
        })
            
        time.sleep(0.1) 

    status.success("3/3: Done!")
    progress.empty()
    return pd.DataFrame(results_data)

# --- 4. UI ---
st.title("🚀 Robust Value Finder")

if st.button("Run Scan"):
    df = run_robust_scan()
    if df is not None:
        # Show the data!
        st.dataframe(
            df, 
            column_config={
                "Ticker": "Symbol",
                "P/B": st.column_config.NumberColumn("Price/Book", format="%.2f"),
                "Sentiment": st.column_config.NumberColumn("Sentiment", format="%.2f"),
            },
            use_container_width=True
        )
