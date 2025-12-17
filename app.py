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

# Fix for TextBlob on Streamlit Cloud
@st.cache_resource
def download_textblob_corpora():
    try:
        subprocess.check_call([sys.executable, "-m", "textblob.download_corpora"])
    except Exception as e:
        st.warning(f"Could not download TextBlob corpora: {e}")

download_textblob_corpora()

# --- 2. SIDEBAR CONTROLS ---
st.sidebar.title("🎛️ Market Filters")
st.sidebar.write("Start with 'Any' to see all stocks, then narrow down.")

# FILTER 1: Market Cap
mc_option = st.sidebar.selectbox(
    "Market Cap", 
    ["Any", "Micro ($50mln to $300mln)", "Small ($300mln to $2bln)", "Mid ($2bln to $10bln)", "Large ($10bln to $200bln)"], 
    index=0
)

# FILTER 2: Valuation (P/E)
pe_option = st.sidebar.selectbox(
    "P/E Ratio (Earnings)", 
    ["Any", "Under 15", "Under 20", "Under 30", "Under 50"], 
    index=0
)

# FILTER 3: Value (P/B)
pb_option = st.sidebar.selectbox(
    "Price/Book (Assets)", 
    ["Any", "Under 1", "Under 2", "Under 3", "Under 5"], 
    index=0
)

# FILTER 4: Financial Health
debt_option = st.sidebar.selectbox(
    "Debt/Equity", 
    ["Any", "Under 0.5", "Under 1"], 
    index=0
)

# FILTER 5: Profitability
profit_option = st.sidebar.selectbox(
    "Net Profit Margin", 
    ["Any", "Positive (>0%)", "High (>20%)"], 
    index=0
)

# SENTIMENT LIMITER
st.sidebar.markdown("---")
max_stocks = st.sidebar.slider("Max Stocks to Analyze (Sentiment)", 5, 50, 10)

# --- 3. MAIN FUNCTION ---
def run_scanner():
    status_text = st.empty()
    status_text.info("🔍 Connecting to Finviz...")
    
    # Build the dictionary. Only add keys if they are NOT "Any"
    filters_dict = {}
    
    if mc_option != "Any": filters_dict['Market Cap.'] = mc_option
    if pe_option != "Any": filters_dict['P/E'] = pe_option
    if pb_option != "Any": filters_dict['P/B'] = pb_option
    if debt_option != "Any": filters_dict['Debt/Equity'] = debt_option
    if profit_option != "Any": filters_dict['Net Profit Margin'] = profit_option

    # Debug line: Uncomment to see what filters are active
    # st.write(f"Active Filters: {filters_dict}")

    foverview = Overview()
    
    try:
        # Apply filters (if any exist)
        if filters_dict:
            foverview.set_filter(filters_dict=filters_dict)
        
        df_results = foverview.screener_view()
        
        if df_results.empty:
            status_text.warning("No stocks found matching these filters.")
            return None
            
    except Exception as e:
        st.error(f"Finviz Error: {e}")
        return None

    status_text.info(f"✅ Found {len(df_results)} stocks. Analyzing sentiment for the top {max_stocks}...")
    
    # Limit the dataframe to the user selection (to save time)
    df_scan = df_results.head(max_stocks)
    
    # Progress Bar
    progress_bar = st.progress(0)
    
    results_data = []
    
    # Iterate for Sentiment
    for index, row in df_scan.iterrows():
        symbol = row['Ticker']
        
        # Update Progress
        progress_bar.progress((index + 1) / len(df_scan))
        
        try:
            stock = yf.Ticker(symbol)
            news = stock.news
            
            sentiment_score = 0
            news_count = 0
            
            if news:
                # Check up to 3 articles per stock
                for article in news[:3]:
                    title = article.get('title', '')
                    blob = TextBlob(title)
                    sentiment_score += blob.sentiment.polarity
                    news_count += 1
                
                if news_count > 0:
                    avg_sentiment = sentiment_score / news_count
                else:
                    avg_sentiment = 0
            else:
                avg_sentiment = 0 # No news
                
            # Create a readable note
            if news_count == 0:
                note = "Silent / Ignored"
            elif avg_sentiment < -0.1:
                note = "Negative News"
            elif avg_sentiment > 0.2:
                note = "Positive News"
            else:
                note = "Neutral"

            results_data.append({
                "Ticker": symbol,
                "Price": row['Price'],
                "P/E": row['P/E'],
                "P/B": row['P/B'],
                "Sector": row['Sector'],
                "Sentiment": round(avg_sentiment, 2),
                "Note": note
            })
            
            # Be polite to API
            time.sleep(0.1)

        except Exception:
            continue
            
    status_text.empty()
    progress_bar.empty()
    
    return pd.DataFrame(results_data)

# --- 4. UI LAYOUT ---
st.title("💰 Deep Value Analyzer")
st.markdown("""
**Instructions:**
1. Leave filters on **"Any"** to start.
2. Click **Run Scan**.
3. Then, slowly add filters (like *Small Cap* or *P/E Under 20*) to narrow it down.
""")

if st.button("Run Scan", type="primary"):
    with st.spinner("Analyzing market data..."):
        df = run_scanner()
        
        if df is not None and not df.empty:
            st.success("Analysis Complete!")
            
            # Formatting the table for display
            st.dataframe(
                df,
                column_config={
                    "Ticker": "Symbol",
                    "P/B": st.column_config.NumberColumn("Price/Book", format="%.2f"),
                    "P/E": st.column_config.NumberColumn("P/E Ratio", format="%.2f"),
                    "Sentiment": st.column_config.NumberColumn("Sentiment", format="%.2f"),
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.error("No results found. Try changing a filter to 'Any'.")
