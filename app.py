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
st.set_page_config(page_title="Market Hunter & Tracker", layout="wide")

@st.cache_resource
def download_textblob_corpora():
    try:
        subprocess.check_call([sys.executable, "-m", "textblob.download_corpora"])
    except Exception as e:
        pass 

download_textblob_corpora()

# --- 2. HELPER FUNCTIONS FOR SAVING DATA ---

def load_portfolio():
    """Loads the portfolio from a CSV file."""
    if os.path.exists('my_portfolio.csv'):
        return pd.read_csv('my_portfolio.csv')
    else:
        # Create an empty dataframe if file doesn't exist
        return pd.DataFrame(columns=['Ticker', 'Date Added', 'Price Added'])

def save_to_portfolio(ticker, current_price):
    """Saves a new stock to the CSV file."""
    df = load_portfolio()
    
    # Check if already exists
    if ticker not in df['Ticker'].values:
        new_row = pd.DataFrame({
            'Ticker': [ticker], 
            'Date Added': [datetime.now().strftime("%Y-%m-%d")],
            'Price Added': [current_price]
        })
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv('my_portfolio.csv', index=False)
        return True
    return False

def remove_from_portfolio(ticker):
    """Removes a stock from the CSV file."""
    df = load_portfolio()
    df = df[df['Ticker'] != ticker]
    df.to_csv('my_portfolio.csv', index=False)

def get_performance_data(ticker):
    """Fetches 1-week and 1-month performance data."""
    try:
        stock = yf.Ticker(ticker)
        # Fetch 2 months of history to ensure we have enough data points
        hist = stock.history(period="2mo")
        
        if hist.empty:
            return None

        current_price = hist['Close'].iloc[-1]
        
        # Get date for 1 week ago
        week_ago_date = datetime.now() - timedelta(days=7)
        # Find nearest trading day index
        week_idx = hist.index.get_indexer([week_ago_date], method='nearest')[0]
        price_1w = hist['Close'].iloc[week_idx]
        
        # Get date for 1 month ago
        month_ago_date = datetime.now() - timedelta(days=30)
        month_idx = hist.index.get_indexer([month_ago_date], method='nearest')[0]
        price_1m = hist['Close'].iloc[month_idx]

        # Calculate % changes
        change_1w = ((current_price - price_1w) / price_1w) * 100
        change_1m = ((current_price - price_1m) / price_1m) * 100
        
        return current_price, change_1w, change_1m
    except Exception:
        return 0, 0, 0

# --- 3. APP NAVIGATION ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["🔍 Market Scanner", "📈 My Portfolio"])

# ==========================================
# PAGE 1: MARKET SCANNER (The Original Tool)
# ==========================================
if page == "🔍 Market Scanner":
    st.title("🌍 True Market Scanner")
    
    # --- SCANNER SETTINGS ---
    st.sidebar.markdown("---")
    st.sidebar.header("Scanner Settings")
    
    strategy = st.sidebar.selectbox(
        "1. Choose Strategy:",
        ["Custom (Manual)", 
         "Insider Buying (Follow the Money)", 
         "Oversold Quality (Dip Buying)", 
         "Short Squeeze (High Risk/Reward)"]
    )
    
    sort_criteria = st.sidebar.selectbox(
        "2. Sort Market By:",
        ["Lowest P/E (Cheapest Earnings)", 
         "Lowest P/B (Cheapest Assets)", 
         "Worst Performance (Biggest Discount)", 
         "Highest Volume (Most Active)"]
    )

    # Manual Filters
    sector_list = ["Any", "Basic Materials", "Communication Services", "Consumer Cyclical", "Consumer Defensive", "Energy", "Financial", "Healthcare", "Industrials", "Real Estate", "Technology", "Utilities"]
    sector_option = st.sidebar.selectbox("Sector", sector_list, index=0)
    
    mc_option = st.sidebar.selectbox("Market Cap", ["Any", "Micro ($50mln to $300mln)", "Small ($300mln to $2bln)", "Mid ($2bln to $10bln)", "Large ($10bln to $200bln)"], index=0)
    
    if strategy == "Custom (Manual)":
        pe_option = st.sidebar.selectbox("P/E Ratio", ["Any", "Under 15", "Under 20", "Under 30"], index=0)
        pb_option = st.sidebar.selectbox("Price/Book", ["Any", "Under 1", "Under 2", "Under 3"], index=0)
        debt_option = st.sidebar.selectbox("Debt/Equity", ["Any", "Under 0.5", "Under 1"], index=0)

    max_stocks = st.sidebar.slider("Max Stocks to Analyze", 5, 20, 10)

    # --- SCANNER LOGIC ---
    if st.button("Run Scan", type="primary"):
        status = st.empty()
        status.info("Scanning Market...")
        
        filters_dict = {}
        
        # Strategy Logic
        if strategy == "Custom (Manual)":
            if sector_option != "Any": filters_dict['Sector'] = sector_option
            if mc_option != "Any": filters_dict['Market Cap.'] = mc_option
            if pe_option != "Any": filters_dict['P/E'] = pe_option
            if pb_option != "Any": filters_dict['P/B'] = pb_option
            if debt_option != "Any": filters_dict['Debt/Equity'] = debt_option
            
        elif strategy == "Insider Buying (Follow the Money)":
            filters_dict['InsiderTransactions'] = 'Positive (>0%)' 
            filters_dict['P/B'] = 'Under 3'
            if mc_option != "Any": filters_dict['Market Cap.'] = mc_option
            
        elif strategy == "Oversold Quality (Dip Buying)":
            filters_dict['RSI (14)'] = 'Oversold (30)'
            filters_dict['Debt/Equity'] = 'Under 0.5'
            filters_dict['Net Profit Margin'] = 'Positive (>0%)'
            if mc_option != "Any": filters_dict['Market Cap.'] = mc_option
    
        elif strategy == "Short Squeeze (High Risk/Reward)":
            filters_dict['Float Short'] = 'High (>20%)'
            filters_dict['Performance'] = 'Today Up'
            if mc_option != "Any": filters_dict['Market Cap.'] = mc_option

        # Run Finviz
        screener = Valuation()
        if filters_dict:
            screener.set_filter(filters_dict=filters_dict)
        
        try:
            if sort_criteria == "Lowest P/E (Cheapest Earnings)": screener.set_sort(key='P/E')
            elif sort_criteria == "Lowest P/B (Cheapest Assets)": screener.set_sort(key='P/B')
            elif sort_criteria == "Worst Performance (Biggest Discount)": screener.set_sort(key='Performance')
            elif sort_criteria == "Highest Volume (Most Active)": screener.set_sort(key='Volume', order='Descending')
            
            df_results = screener.screener_view()
        except Exception as e:
            st.error(f"Finviz Error: {e}")
            df_results = pd.DataFrame()

        if not df_results.empty:
            status.success(f"Found {len(df_results)} stocks.")
            
            # --- DISPLAY RESULTS WITH "ADD" BUTTONS ---
            st.write("### Scan Results")
            st.write("Click 'Add' to save to your portfolio.")
            
            # We iterate through the rows to create buttons
            # We use columns to make the layout look like a table
            for index, row in df_results.head(max_stocks).iterrows():
                col1, col2, col3, col4, col5 = st.columns([1, 2, 1, 1, 1])
                
                with col1:
                    st.write(f"**{row['Ticker']}**")
                with col2:
                    st.write(f"${row['Price']}")
                with col3:
                    st.write(f"P/E: {row.get('P/E', 'N/A')}")
                with col4:
                    st.write(f"P/B: {row.get('P/B', 'N/A')}")
                with col5:
                    # THE MAGIC BUTTON
                    # We use a unique key for each button so Streamlit doesn't get confused
                    if st.button(f"Add {row['Ticker']}", key=f"add_{row['Ticker']}"):
                        if save_to_portfolio(row['Ticker'], row['Price']):
                            st.toast(f"✅ Added {row['Ticker']} to Portfolio!")
                        else:
                            st.toast(f"⚠️ {row['Ticker']} is already in portfolio.")
                st.divider()
        else:
            status.warning("No stocks found.")

# ==========================================
# PAGE 2: MY PORTFOLIO (The Tracker)
# ==========================================
elif page == "📈 My Portfolio":
    st.title("📈 My Stock Tracker")
    st.markdown("Track the performance of your saved stocks over time.")
    
    df_portfolio = load_portfolio()
    
    if df_portfolio.empty:
        st.info("Your portfolio is empty. Go to the **Scanner** and add some stocks!")
    else:
        if st.button("🔄 Refresh Prices"):
            st.rerun()
            
        st.write(f"Tracking **{len(df_portfolio)}** stocks.")
        
        results = []
        progress = st.progress(0)
        
        # Loop through your saved stocks
        for i, (index, row) in enumerate(df_portfolio.iterrows()):
            ticker = row['Ticker']
            progress.progress((i + 1) / len(df_portfolio))
            
            # Fetch real-time performance
            cur_price, chg_1w, chg_1m = get_performance_data(ticker)
            
            # Calculate Total Return since you added it
            price_added = float(row['Price Added'])
            
            if price_added > 0:
                total_return = ((cur_price - price_added) / price_added) * 100
            else:
                total_return = 0
            
            results.append({
                "Ticker": ticker,
                "Current Price": cur_price,
                "Price Added": price_added,
                "Total Return": total_return,
                "1 Week %": chg_1w,
                "1 Month %": chg_1m,
                "Date Added": row['Date Added']
            })
            
            time.sleep(0.1) # Be polite to the API
            
        progress.empty()
        
        # Display the Portfolio Table
        res_df = pd.DataFrame(results)
        
        # Formatting with Color for Returns
        st.dataframe(
            res_df,
            column_config={
                "Ticker": "Symbol",
                "Current Price": st.column_config.NumberColumn("Current Price", format="$%.2f"),
                "Price Added": st.column_config.NumberColumn("Cost Basis", format="$%.2f"),
                "Total Return": st.column_config.NumberColumn("Total Return", format="%.2f%%"),
                "1 Week %": st.column_config.NumberColumn("1 Week Chg", format="%.2f%%"),
                "1 Month %": st.column_config.NumberColumn("1 Month Chg", format="%.2f%%"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Delete functionality
        st.subheader("Manage Portfolio")
        to_remove = st.selectbox("Select stock to remove:", ["Select..."] + list(df_portfolio['Ticker']))
        if st.button("Remove Stock"):
            if to_remove != "Select...":
                remove_from_portfolio(to_remove)
                st.success(f"Removed {to_remove}")
                time.sleep(1)
                st.rerun()
