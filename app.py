import streamlit as st
import pandas as pd
from finvizfinance.screener.valuation import Valuation
import yfinance as yf
from textblob import TextBlob
import time
import subprocess
import sys

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Deep Value Analyzer", layout="wide")

# Fix for TextBlob on Streamlit Cloud
@st.cache_resource
def download_textblob_corpora():
    try:
        subprocess.check_call([sys.executable, "-m", "textblob.download_corpora"])
    except Exception as e:
        pass 

download_textblob_corpora()

# --- 2. SIDEBAR FILTERS ---
st.sidebar.title("🎛️ Market Filters")
st.sidebar.write("Set filters to 'Any' to see the broad market.")

# FILTER: Sector (New!)
sector_list = [
    "Any", "Basic Materials", "Communication Services", "Consumer Cyclical", 
    "Consumer Defensive", "Energy", "Financial", "Healthcare", "Industrials", 
    "Real Estate", "Technology", "Utilities"
]
sector_option = st.sidebar.selectbox("Sector", sector_list, index=0)

# FILTER: Market Cap (Expanded!)
mc_list = [
    "Any", 
    "Micro ($50mln to $300mln)", 
    "Small ($300mln to $2bln)", 
    "Mid ($2bln to $10bln)", 
    "Large ($10bln to $200bln)", 
    "Mega ($200bln and more)"
]
mc_option = st.sidebar.selectbox("Market Cap", mc_list, index=0)

# FILTER: Valuation
pe_option = st.sidebar.selectbox("P/E Ratio", ["Any", "Under 15", "Under 20", "Under 30", "Under 50"], index=0)
pb_option = st.sidebar.selectbox("Price/Book", ["Any", "Under 1", "Under 2", "Under 3", "Under 5"], index=0)

# FILTER: Health
debt_option = st.sidebar.selectbox("Debt/Equity", ["Any", "Under 0.5", "Under 1"], index=0)

# LIMITER
max_stocks = st.sidebar.slider("Number of stocks to analyze", 5, 20, 10)

# --- 3. SCANNING LOGIC ---
def run_scan():
    status = st.empty()
    status.info("1/3: Connecting to Finviz...")
    
    # Build Filter Dictionary
    filters_dict = {}
    
    if sector_option != "Any": filters_dict['Sector'] = sector_option
    if mc_option != "Any": filters_dict['Market Cap.'] = mc_option
    if pe_option != "Any": filters_dict['P/E'] = pe_option
    if pb_option != "Any": filters_dict['P/B'] = pb_option
    if debt_option != "Any": filters_dict['Debt/Equity'] = debt_option

    # Initialize Screener (Valuation View for P/B & P/E)
    screener = Valuation()
    
    # If filters exist, apply them. If empty, it fetches default list (Top 20).
    if filters_dict:
        screener.set_filter(filters_dict=filters_dict)
    
    try:
        # Fetch data
        df_results = screener.screener_view()
        
        if df_results.empty:
            status.warning("No stocks found matching these criteria.")
            return None
            
    except Exception as e:
        # If Finviz blocks us or errors out
        status.error(f"Error fetching data: {e}")
        return None

    status.info(f"2/3: Found {len(df_results)} candidates. Analyzing top {max_stocks}...")
    
    # Slice the dataframe to the user's limit
    df_scan = df_results.head(max_stocks)
    results_data = []
    
    progress = st.progress(0)
    
    # Iterate through stocks
    for i, (index, row) in enumerate(df_scan.iterrows()):
        symbol = row['Ticker']
        progress.progress((i + 1) / len(df_scan))
        
        # Placeholders
        sentiment_score = 0.0
        sector_name = "N/A"
        note = "N/A"
        
        try:
            # Connect to Yahoo Finance
            stock = yf.Ticker(symbol)
            
            # 1. Get Sector (Since Valuation view doesn't have it)
            # We try to get it from Yahoo Info
            try:
                sector_name = stock.info.get('sector', 'Unknown')
            except:
                sector_name = "Unknown"

            # 2. Get News & Sentiment
            news = stock.news
            if news:
                title = news[0].get('title', '')
                sentiment_score = TextBlob(title).sentiment.polarity
                note = "News Analyzed"
            else:
                note = "No News"
                
        except Exception:
            note = "Connection Error"

        # Safe conversion of P/B (sometimes it's a string or '-')
        try:
            pb_val = float(row.get('P/B', 0))
        except:
            pb_val = 0

        # Build row
        results_data.append({
            "Ticker": symbol,
            "Price": row.get('Price', 'N/A'),
            "P/E": row.get('P/E', 'N/A'),
            "P/B": pb_val, 
            "Sector": sector_name,  # From Yahoo
            "Sentiment": round(sentiment_score, 2)
        })
        
        # Sleep to avoid rate limits
        time.sleep(0.2)

    status.success("3/3: Scan Complete!")
    progress.empty()
    
    return pd.DataFrame(results_data)

# --- 4. APP UI ---
st.title("💰 Deep Value Finder")
st.markdown("""
**How to find hidden value:**
1.  **Start Broad:** Leave filters as "Any" to see if the connection works.
2.  **Narrow Down:** Select a **Sector** (like 'Financial' or 'Industrials').
3.  **Find Value:** Set **Price/Book** to 'Under 2' or 'Under 1'.
""")

if st.button("Run Scan", type="primary"):
    df = run_scan()
    
    if df is not None and not df.empty:
        # Display Dataframe with nice formatting
        st.dataframe(
            df, 
            column_config={
                "Ticker": "Symbol",
                "P/B": st.column_config.NumberColumn("Price/Book", format="%.2f"),
                "P/E": st.column_config.NumberColumn("P/E Ratio", format="%.2f"),
                "Sentiment": st.column_config.NumberColumn("Sentiment Score", format="%.2f"),
                "Sector": "Industry Sector"
            },
            use_container_width=True,
            hide_index=True
        )
