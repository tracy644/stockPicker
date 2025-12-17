import streamlit as st
import pandas as pd
from finvizfinance.screener.overview import Overview
import yfinance as yf
from textblob import TextBlob
import time
import subprocess
import sys

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Stock Screener & Debugger", layout="wide")

# Fix for TextBlob
@st.cache_resource
def download_textblob_corpora():
    try:
        subprocess.check_call([sys.executable, "-m", "textblob.download_corpora"])
    except Exception as e:
        st.warning(f"Could not download TextBlob corpora: {e}")

download_textblob_corpora()

# --- 2. SIDEBAR FILTERS ---
st.sidebar.title("🎛️ Settings")

# We use "Any" as the default for everything to test if it works
mc_option = st.sidebar.selectbox("Market Cap", ["Any", "Small ($300mln to $2bln)", "Micro ($50mln to $300mln)"], index=0)
pe_option = st.sidebar.selectbox("P/E Ratio", ["Any", "Under 15", "Under 20", "Under 30"], index=0)
pb_option = st.sidebar.selectbox("Price/Book", ["Any", "Under 1", "Under 2", "Under 3"], index=0)
debt_option = st.sidebar.selectbox("Debt/Equity", ["Any", "Under 0.5", "Under 1"], index=0)
profit_option = st.sidebar.selectbox("Net Profit Margin", ["Any", "Positive (>0%)", "High (>20%)"], index=0)

# --- 3. FUNCTIONS ---

def test_connection():
    """Tries to just fetch the default 'Top Gainers' list to see if Finviz is blocked."""
    st.info("🔌 Testing connection to Finviz...")
    try:
        # We use a signal (Top Gainers) just to see if we can get ANY data
        foverview = Overview()
        foverview.set_filter(signal='Top Gainers') 
        df = foverview.screener_view()
        st.success(f"✅ Connection Successful! Retrieved {len(df)} stocks (Top Gainers).")
        st.dataframe(df.head(3))
        return True
    except Exception as e:
        st.error(f"❌ Connection Failed. Finviz might be blocking this IP.\nError: {e}")
        return False

def get_stocks():
    status_text = st.empty()
    status_text.info("🔍 screening...")
    
    # 1. Build Filters
    filters_dict = {}
    
    if mc_option != "Any": filters_dict['Market Cap.'] = mc_option
    if pe_option != "Any": filters_dict['P/E'] = pe_option
    if pb_option != "Any": filters_dict['P/B'] = pb_option
    if debt_option != "Any": filters_dict['Debt/Equity'] = debt_option
    if profit_option != "Any": filters_dict['Net Profit Margin'] = profit_option

    # DEBUG: Show user what we are sending
    with st.expander("View Debug Info (Active Filters)"):
        st.write("Filters being sent to Finviz:", filters_dict)
        if not filters_dict:
            st.warning("⚠️ No filters selected! Fetching default list (first 20).")

    # 2. Run Screen
    foverview = Overview()
    
    try:
        if filters_dict:
            foverview.set_filter(filters_dict=filters_dict)
        
        # If no filters, this fetches the default landing page of the screener
        df_results = foverview.screener_view()
        
        if df_results.empty:
            return None
            
        return df_results
        
    except Exception as e:
        st.error(f"Error from Finviz: {e}")
        return None

# --- 4. UI ---
st.title("🧪 Value Hunter (Diagnostic Mode)")
st.write("If you see no results, try the 'Test Connection' button first.")

col1, col2 = st.columns(2)

with col1:
    if st.button("🔌 Test Connection (Click First)"):
        test_connection()

with col2:
    if st.button("🚀 Run Screener"):
        df = get_stocks()
        
        if df is not None and not df.empty:
            st.success(f"Found {len(df)} stocks.")
            
            # Sentiment Analysis on top 5 only (to be fast)
            st.write("Analyzing sentiment on top 5 results...")
            
            results = []
            for index, row in df.head(5).iterrows():
                symbol = row['Ticker']
                try:
                    stock = yf.Ticker(symbol)
                    news = stock.news
                    sentiment = 0
                    if news:
                        title = news[0].get('title', '')
                        sentiment = TextBlob(title).sentiment.polarity
                    
                    results.append({
                        "Ticker": symbol, 
                        "Price": row['Price'], 
                        "P/B": row['P/B'], 
                        "Sentiment": round(sentiment, 2)
                    })
                    time.sleep(0.1)
                except:
                    pass
            
            st.table(pd.DataFrame(results))
            st.dataframe(df)
        else:
            st.warning("No stocks found (or connection blocked).")
