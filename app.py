import streamlit as st
import pandas as pd
from finvizfinance.screener.valuation import Valuation
import yfinance as yf
from textblob import TextBlob
import time
import subprocess
import sys

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Value Winner Finder", layout="wide")

# Fix for TextBlob
@st.cache_resource
def download_textblob_corpora():
    try:
        subprocess.check_call([sys.executable, "-m", "textblob.download_corpora"])
    except Exception as e:
        pass 

download_textblob_corpora()

# --- 2. SIDEBAR STRATEGIES ---
st.sidebar.title("🏆 Rank by Winner")
st.sidebar.markdown("Auto-sorts results to find the highest potential.")

# STRATEGY SELECTOR
strategy = st.sidebar.selectbox(
    "Select Strategy:",
    ["Custom (Manual)", 
     "1. Insider Buying (Follow the Money)", 
     "2. Oversold Quality (Dip Buying)", 
     "3. Short Squeeze (High Risk/Reward)"]
)

# SORTING PREFERENCE
sort_by = st.sidebar.radio(
    "Rank Winners By:",
    ["Discount from 52-Week High", "Analyst Upside Potential", "Lowest P/E Ratio"]
)

st.sidebar.markdown("---")
st.sidebar.header("🛠️ Manual Filters")

# Manual Filters
sector_list = ["Any", "Basic Materials", "Communication Services", "Consumer Cyclical", "Consumer Defensive", "Energy", "Financial", "Healthcare", "Industrials", "Real Estate", "Technology", "Utilities"]
sector_option = st.sidebar.selectbox("Sector", sector_list, index=0)

mc_option = st.sidebar.selectbox("Market Cap", ["Any", "Micro ($50mln to $300mln)", "Small ($300mln to $2bln)", "Mid ($2bln to $10bln)", "Large ($10bln to $200bln)"], index=0)

if strategy == "Custom (Manual)":
    pe_option = st.sidebar.selectbox("P/E Ratio", ["Any", "Under 15", "Under 20", "Under 30"], index=0)
    pb_option = st.sidebar.selectbox("Price/Book", ["Any", "Under 1", "Under 2", "Under 3"], index=0)
    debt_option = st.sidebar.selectbox("Debt/Equity", ["Any", "Under 0.5", "Under 1"], index=0)
else:
    st.sidebar.info(f"Filters locked for '{strategy}'.")

# LIMITER
max_stocks = st.sidebar.slider("Max Stocks to Analyze", 5, 20, 10)

# --- 3. SCANNING LOGIC ---
def run_scan():
    status = st.empty()
    status.info("1/3: Screening Market...")
    
    filters_dict = {}
    
    # APPLY STRATEGY FILTERS
    if strategy == "Custom (Manual)":
        if sector_option != "Any": filters_dict['Sector'] = sector_option
        if mc_option != "Any": filters_dict['Market Cap.'] = mc_option
        if pe_option != "Any": filters_dict['P/E'] = pe_option
        if pb_option != "Any": filters_dict['P/B'] = pb_option
        if debt_option != "Any": filters_dict['Debt/Equity'] = debt_option
        
    elif strategy == "1. Insider Buying (Follow the Money)":
        filters_dict['InsiderTransactions'] = 'Positive (>0%)' 
        filters_dict['P/B'] = 'Under 3'
        if mc_option != "Any": filters_dict['Market Cap.'] = mc_option
        if sector_option != "Any": filters_dict['Sector'] = sector_option
        
    elif strategy == "2. Oversold Quality (Dip Buying)":
        filters_dict['RSI (14)'] = 'Oversold (30)'
        filters_dict['Debt/Equity'] = 'Under 0.5'
        filters_dict['Net Profit Margin'] = 'Positive (>0%)'
        if mc_option != "Any": filters_dict['Market Cap.'] = mc_option

    elif strategy == "3. Short Squeeze (High Risk/Reward)":
        filters_dict['Float Short'] = 'High (>20%)'
        filters_dict['Performance'] = 'Today Up'
        if mc_option != "Any": filters_dict['Market Cap.'] = mc_option

    # Initialize Screener
    screener = Valuation()
    if filters_dict:
        screener.set_filter(filters_dict=filters_dict)
    
    try:
        df_results = screener.screener_view()
        if df_results.empty:
            status.warning("No stocks matched. Try looser filters.")
            return None
    except Exception as e:
        status.error(f"Error fetching data: {e}")
        return None

    status.info(f"2/3: Found {len(df_results)} candidates. Calculating Upside & 52W Highs...")
    
    df_scan = df_results.head(max_stocks)
    results_data = []
    
    progress = st.progress(0)
    
    for i, (index, row) in enumerate(df_scan.iterrows()):
        symbol = row['Ticker']
        progress.progress((i + 1) / len(df_scan))
        
        # Placeholders
        sentiment_score = 0.0
        sector_name = "N/A"
        high_52 = 0
        analyst_target = 0
        current_price = 0
        
        try:
            # Fetch Yahoo Data
            stock = yf.Ticker(symbol)
            info = stock.info
            
            # 1. Get Sector
            sector_name = info.get('sector', 'Unknown')
            
            # 2. Get Price Data for Ranking
            current_price = info.get('currentPrice', row.get('Price', 0))
            high_52 = info.get('fiftyTwoWeekHigh', 0)
            analyst_target = info.get('targetMeanPrice', 0)
            
            # 3. Get News Sentiment
            news = stock.news
            if news:
                title = news[0].get('title', '')
                sentiment_score = TextBlob(title).sentiment.polarity

        except Exception:
            pass

        # Parse Finviz Numbers
        try: pb_val = float(row.get('P/B', 0))
        except: pb_val = 0
        try: pe_val = float(row.get('P/E', 0))
        except: pe_val = 999 # Make it high so it sorts last if missing

        # Calculate Metrics
        # Discount: How much lower is it than the 52 week high?
        if high_52 > 0 and current_price > 0:
            discount_pct = ((high_52 - current_price) / high_52) * 100
        else:
            discount_pct = 0
            
        # Upside: How much higher is the analyst target?
        if analyst_target > 0 and current_price > 0:
            upside_pct = ((analyst_target - current_price) / current_price) * 100
        else:
            upside_pct = 0

        results_data.append({
            "Ticker": symbol,
            "Price": current_price,
            "P/E": pe_val,
            "P/B": pb_val, 
            "Sector": sector_name,
            "52W High": high_52,
            "Discount": round(discount_pct, 1),      # Sort Key 1
            "Analyst Target": analyst_target,
            "Upside %": round(upside_pct, 1),        # Sort Key 2
            "Sentiment": round(sentiment_score, 2)
        })
        
        time.sleep(0.2)

    status.success(f"3/3: Scan Complete! Ranked by {sort_by}.")
    progress.empty()
    
    # Create DataFrame
    final_df = pd.DataFrame(results_data)
    
    # --- SORTING LOGIC ---
    if not final_df.empty:
        if sort_by == "Discount from 52-Week High":
            # Sort Descending (Higher discount is better for value)
            final_df = final_df.sort_values(by='Discount', ascending=False)
        elif sort_by == "Analyst Upside Potential":
            # Sort Descending (Higher upside is better)
            final_df = final_df.sort_values(by='Upside %', ascending=False)
        elif sort_by == "Lowest P/E Ratio":
            # Sort Ascending (Lower P/E is better)
            final_df = final_df.sort_values(by='P/E', ascending=True)

    return final_df

# --- 4. APP UI ---
st.title("🏆 Winner Finder")
st.markdown("""
**New Columns Explained:**
*   **Discount:** How far the stock has fallen from its peak. (e.g., 50% means it's half off).
*   **Upside %:** If analysts are right, how much money could you make?
""")

if st.button("Find Winners", type="primary"):
    df = run_scan()
    
    if df is not None and not df.empty:
        st.dataframe(
            df, 
            column_config={
                "Ticker": "Symbol",
                "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
                "52W High": st.column_config.NumberColumn("52W High", format="$%.2f"),
                "Discount": st.column_config.NumberColumn("Discount (Off High)", format="%.1f%%"),
                "Analyst Target": st.column_config.NumberColumn("Target Price", format="$%.2f"),
                "Upside %": st.column_config.NumberColumn("Analyst Upside", format="%.1f%%"),
                "Sentiment": st.column_config.NumberColumn("Sentiment", format="%.2f"),
            },
            use_container_width=True,
            hide_index=True
        )
