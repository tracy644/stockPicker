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

# --- 2. HELPER FUNCTIONS ---

def load_portfolio():
    if os.path.exists('my_portfolio.csv'):
        return pd.read_csv('my_portfolio.csv')
    else:
        return pd.DataFrame(columns=['Ticker', 'Date Added', 'Price Added'])

def save_to_portfolio(ticker, current_price):
    df = load_portfolio()
    try:
        current_price = float(current_price)
    except:
        current_price = 0.0
        
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
    df = load_portfolio()
    df = df[df['Ticker'] != ticker]
    df.to_csv('my_portfolio.csv', index=False)

def get_performance_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="2mo")
        if hist.empty: return None
        
        current_price = hist['Close'].iloc[-1]
        
        week_ago = datetime.now() - timedelta(days=7)
        week_idx = hist.index.get_indexer([week_ago], method='nearest')[0]
        price_1w = hist['Close'].iloc[week_idx]
        
        month_ago = datetime.now() - timedelta(days=30)
        month_idx = hist.index.get_indexer([month_ago], method='nearest')[0]
        price_1m = hist['Close'].iloc[month_idx]

        change_1w = ((current_price - price_1w) / price_1w) * 100
        change_1m = ((current_price - price_1m) / price_1m) * 100
        
        return current_price, change_1w, change_1m
    except:
        return 0, 0, 0

# --- 3. APP NAVIGATION ---
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["🔍 Market Scanner", "📈 My Portfolio"])

# ==========================================
# PAGE 1: MARKET SCANNER
# ==========================================
if page == "🔍 Market Scanner":
    st.title("🌍 True Market Scanner")
    
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
         "Worst Performance (Biggest Discount)"]
    )

    sector_list = ["Any", "Basic Materials", "Communication Services", "Consumer Cyclical", "Consumer Defensive", "Energy", "Financial", "Healthcare", "Industrials", "Real Estate", "Technology", "Utilities"]
    sector_option = st.sidebar.selectbox("Sector", sector_list, index=0)
    
    mc_option = st.sidebar.selectbox("Market Cap", ["Any", "Micro ($50mln to $300mln)", "Small ($300mln to $2bln)", "Mid ($2bln to $10bln)", "Large ($10bln to $200bln)"], index=0)
    
    if strategy == "Custom (Manual)":
        pe_option = st.sidebar.selectbox("P/E Ratio", ["Any", "Under 15", "Under 20", "Under 30"], index=0)
        pb_option = st.sidebar.selectbox("Price/Book", ["Any", "Under 1", "Under 2", "Under 3"], index=0)
        debt_option = st.sidebar.selectbox("Debt/Equity", ["Any", "Under 0.5", "Under 1"], index=0)

    max_stocks = st.sidebar.slider("Max Stocks to Analyze", 5, 20, 10)

    # Initialize session state for results
    if 'scan_results' not in st.session_state:
        st.session_state['scan_results'] = None

    if st.button("Run Scan", type="primary"):
        status = st.empty()
        status.info("Step 1: Screening Market via Finviz...")
        
        filters_dict = {}
        
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

        screener = Valuation()
        if filters_dict:
            screener.set_filter(filters_dict=filters_dict)
        
        sort_map = {
            "Lowest P/E (Cheapest Earnings)": "Price/Earnings",
            "Lowest P/B (Cheapest Assets)": "Price/Book",
            "Worst Performance (Biggest Discount)": "Performance (Year)"
        }
        sort_key = sort_map.get(sort_criteria, 'Price/Earnings')

        try:
            df_results = screener.screener_view(order=sort_key)
            
            if not df_results.empty:
                # --- ENRICH DATA HERE (RUNS ONCE) ---
                status.info(f"Step 2: Found {len(df_results)} stocks. Calculating Discounts...")
                
                enriched_data = []
                subset = df_results.head(max_stocks)
                
                progress = st.progress(0)
                for i, (index, row) in enumerate(subset.iterrows()):
                    progress.progress((i + 1) / len(subset))
                    
                    # Fetch 52 Week Data
                    discount_str = "-"
                    try:
                        tinfo = yf.Ticker(row['Ticker']).info
                        high_52 = tinfo.get('fiftyTwoWeekHigh', 0)
                        curr_p = tinfo.get('currentPrice', row.get('Price', 0))
                        
                        if high_52 and high_52 > 0:
                            disc = ((high_52 - curr_p) / high_52) * 100
                            discount_str = f"🔻 {disc:.1f}%"
                    except:
                        pass
                        
                    # Build Row for Session State
                    enriched_data.append({
                        'Ticker': row['Ticker'],
                        'Price': row.get('Price', 0),
                        'P/E': row.get('P/E', '-'),
                        'P/B': row.get('P/B', '-'),
                        'Discount_Str': discount_str
                    })
                    time.sleep(0.1)
                
                progress.empty()
                st.session_state['scan_results'] = pd.DataFrame(enriched_data)
                status.success("Scan Complete!")
                
            else:
                st.session_state['scan_results'] = pd.DataFrame()
                status.warning("No stocks found.")
                
        except Exception as e:
            st.error(f"Finviz Error: {e}")
            st.session_state['scan_results'] = pd.DataFrame()

    # --- DISPLAY RESULTS FROM MEMORY ---
    if st.session_state['scan_results'] is not None and not st.session_state['scan_results'].empty:
        
        df_display = st.session_state['scan_results']
        
        st.write("### Scan Results")
        
        # Headers
        h1, h2, h3, h4, h5, h6 = st.columns([1, 1, 1.5, 1, 1, 1])
        h1.markdown("**Ticker**")
        h2.markdown("**Price**")
        h3.markdown("**52W Discount**")
        h4.markdown("**P/E**")
        h5.markdown("**P/B**")
        h6.markdown("**Action**")
        st.divider()
        
        for i, (index, row) in enumerate(df_display.iterrows()):
            c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1.5, 1, 1, 1])
            
            c1.write(f"**{row['Ticker']}**")
            c2.write(f"${row['Price']}")
            c3.write(f"**{row['Discount_Str']}**") # <--- Shows calculated value
            c4.write(f"{row['P/E']}")
            c5.write(f"{row['P/B']}")
            
            # CALLBACK FUNCTION
            def add_stock_callback(t, p):
                if save_to_portfolio(t, p):
                    st.toast(f"✅ Saved {t}!")
                else:
                    st.toast(f"⚠️ {t} already saved.")
            
            c6.button(f"Add", key=f"btn_{row['Ticker']}", on_click=add_stock_callback, args=(row['Ticker'], row['Price']))
            
            st.divider()

# ==========================================
# PAGE 2: MY PORTFOLIO
# ==========================================
elif page == "📈 My Portfolio":
    st.title("📈 My Stock Tracker")
    
    df_portfolio = load_portfolio()
    
    if df_portfolio.empty:
        st.info("Your portfolio is empty. Go to the **Scanner** to find stocks.")
    else:
        if st.button("🔄 Refresh Prices"):
            st.rerun()
            
        st.write(f"Tracking **{len(df_portfolio)}** stocks.")
        
        results = []
        progress = st.progress(0)
        
        for i, (index, row) in enumerate(df_portfolio.iterrows()):
            ticker = row['Ticker']
            progress.progress((i + 1) / len(df_portfolio))
            
            cur_price, chg_1w, chg_1m = get_performance_data(ticker)
            
            try:
                price_added = float(row['Price Added'])
            except:
                price_added = 0.0
                
            if price_added > 0 and cur_price > 0:
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
            time.sleep(0.1)
            
        progress.empty()
        
        res_df = pd.DataFrame(results)
        
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
        
        st.subheader("Manage Portfolio")
        to_remove = st.selectbox("Select stock to remove:", ["Select..."] + list(df_portfolio['Ticker']))
        if st.button("Remove Stock"):
            if to_remove != "Select...":
                remove_from_portfolio(to_remove)
                st.success(f"Removed {to_remove}")
                time.sleep(1)
                st.rerun()
