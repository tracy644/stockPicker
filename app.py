import streamlit as st
import pandas as pd
from finvizfinance.screener.valuation import Valuation
import yfinance as yf
from textblob import TextBlob
import time
import subprocess
import sys

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Insider Value Hunter", layout="wide")

# Fix for TextBlob
@st.cache_resource
def download_textblob_corpora():
    try:
        subprocess.check_call([sys.executable, "-m", "textblob.download_corpora"])
    except Exception as e:
        pass 

download_textblob_corpora()

# --- 2. SIDEBAR STRATEGIES ---
st.sidebar.title("🕵️ Secret Sauce Strategies")
st.sidebar.markdown("Select a strategy to auto-fill filters, or choose 'Custom' to build your own.")

# THE SECRET SAUCE SELECTOR
strategy = st.sidebar.selectbox(
    "Choose your Edge:",
    ["Custom (Manual)", 
     "1. Insider Buying (Follow the Money)", 
     "2. Oversold Quality (Dip Buying)", 
     "3. Short Squeeze (High Risk/Reward)"]
)

st.sidebar.markdown("---")
st.sidebar.header("🛠️ Manual Filters")

# Standard Filters (These are active if 'Custom' is selected, or refine the Strategies)
sector_list = ["Any", "Basic Materials", "Communication Services", "Consumer Cyclical", "Consumer Defensive", "Energy", "Financial", "Healthcare", "Industrials", "Real Estate", "Technology", "Utilities"]
sector_option = st.sidebar.selectbox("Sector", sector_list, index=0)

mc_option = st.sidebar.selectbox("Market Cap", ["Any", "Micro ($50mln to $300mln)", "Small ($300mln to $2bln)", "Mid ($2bln to $10bln)", "Large ($10bln to $200bln)"], index=0)

# We hide these specific controls if a Strategy is selected to avoid confusion, 
# but we keep them available for Custom mode.
if strategy == "Custom (Manual)":
    pe_option = st.sidebar.selectbox("P/E Ratio", ["Any", "Under 15", "Under 20", "Under 30"], index=0)
    pb_option = st.sidebar.selectbox("Price/Book", ["Any", "Under 1", "Under 2", "Under 3"], index=0)
    debt_option = st.sidebar.selectbox("Debt/Equity", ["Any", "Under 0.5", "Under 1"], index=0)
else:
    st.sidebar.info(f"Filters are locked for '{strategy}' strategy.")

# LIMITER
max_stocks = st.sidebar.slider("Max Stocks to Analyze", 5, 20, 10)

# --- 3. SCANNING LOGIC ---
def run_scan():
    status = st.empty()
    status.info("1/3: Applying Strategy & Connecting to Finviz...")
    
    filters_dict = {}
    
    # --- APPLYING THE SECRET SAUCE ---
    if strategy == "Custom (Manual)":
        # Use whatever the user picked manually
        if sector_option != "Any": filters_dict['Sector'] = sector_option
        if mc_option != "Any": filters_dict['Market Cap.'] = mc_option
        if pe_option != "Any": filters_dict['P/E'] = pe_option
        if pb_option != "Any": filters_dict['P/B'] = pb_option
        if debt_option != "Any": filters_dict['Debt/Equity'] = debt_option
        
    elif strategy == "1. Insider Buying (Follow the Money)":
        # Logic: Small Caps + Cheap + Insiders are BUYING
        filters_dict['InsiderTransactions'] = 'Positive (>0%)' 
        filters_dict['P/B'] = 'Under 3' # Ensure it's not totally overvalued
        if mc_option != "Any": filters_dict['Market Cap.'] = mc_option
        if sector_option != "Any": filters_dict['Sector'] = sector_option
        
    elif strategy == "2. Oversold Quality (Dip Buying)":
        # Logic: Profitable + Low Debt + RSI < 30 (Beaten down unfairly)
        filters_dict['RSI (14)'] = 'Oversold (30)'
        filters_dict['Debt/Equity'] = 'Under 0.5'
        filters_dict['Net Profit Margin'] = 'Positive (>0%)'
        if mc_option != "Any": filters_dict['Market Cap.'] = mc_option
        if sector_option != "Any": filters_dict['Sector'] = sector_option

    elif strategy == "3. Short Squeeze (High Risk/Reward)":
        # Logic: High Short Interest + Price Moving UP (Squeeze trigger)
        filters_dict['Float Short'] = 'High (>20%)'
        filters_dict['Performance'] = 'Today Up' # Price must be moving up today to trigger fear in shorts
        if mc_option != "Any": filters_dict['Market Cap.'] = mc_option

    # Initialize Screener
    screener = Valuation()
    
    if filters_dict:
        screener.set_filter(filters_dict=filters_dict)
    
    try:
        df_results = screener.screener_view()
        if df_results.empty:
            status.warning("No stocks matched this strategy today. (Strategies are strict!)")
            return None
    except Exception as e:
        status.error(f"Error fetching data: {e}")
        return None

    status.info(f"2/3: Found {len(df_results)} candidates. Analyzing top {max_stocks}...")
    
    # Slice dataframe
    df_scan = df_results.head(max_stocks)
    results_data = []
    
    progress = st.progress(0)
    
    for i, (index, row) in enumerate(df_scan.iterrows()):
        symbol = row['Ticker']
        progress.progress((i + 1) / len(df_scan))
        
        sentiment_score = 0.0
        sector_name = "N/A"
        
        try:
            stock = yf.Ticker(symbol)
            try:
                sector_name = stock.info.get('sector', 'Unknown')
            except:
                sector_name = "Unknown"

            news = stock.news
            if news:
                title = news[0].get('title', '')
                sentiment_score = TextBlob(title).sentiment.polarity
        except Exception:
            pass

        # Safe Data Handling
        try: pb_val = float(row.get('P/B', 0))
        except: pb_val = 0
            
        results_data.append({
            "Ticker": symbol,
            "Price": row.get('Price', 'N/A'),
            "P/E": row.get('P/E', 'N/A'),
            "P/B": pb_val, 
            "Sector": sector_name,
            "Sentiment": round(sentiment_score, 2),
            "Reason": get_strategy_reason(strategy, row)
        })
        
        time.sleep(0.2)

    status.success(f"3/3: Scan Complete! Strategy: {strategy}")
    progress.empty()
    
    return pd.DataFrame(results_data)

def get_strategy_reason(strat, row):
    if "Insider" in strat: return "Insiders Buying"
    if "Oversold" in strat: return "RSI < 30 (Oversold)"
    if "Short" in strat: return "High Short Interest"
    return "Custom Filter"

# --- 4. APP UI ---
st.title("🕵️ Insider Value Hunter")
st.markdown("""
**How to use the Secret Sauce:**
1.  **Insider Buying:** Finds companies where management is buying their own stock. (Highest confidence signal).
2.  **Oversold Quality:** Finds good profitable companies that were sold off too hard (RSI < 30).
3.  **Short Squeeze:** High risk. Finds hated stocks that are starting to rally, forcing sellers to cover.
""")

if st.button("Run Strategy Scan", type="primary"):
    df = run_scan()
    
    if df is not None and not df.empty:
        st.dataframe(
            df, 
            column_config={
                "Ticker": "Symbol",
                "P/B": st.column_config.NumberColumn("Price/Book", format="%.2f"),
                "P/E": st.column_config.NumberColumn("P/E Ratio", format="%.2f"),
                "Sentiment": st.column_config.NumberColumn("Sentiment Score", format="%.2f"),
                "Reason": "Why it matched"
            },
            use_container_width=True,
            hide_index=True
        )
