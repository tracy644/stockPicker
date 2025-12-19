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
page = st.sidebar.radio("Go to:", ["🔍 Market Scanner", "📈 My Portfolio", "⚖️ Stock Analyst"])

# ==========================================
# PAGE: MARKET SCANNER
# ==========================================
if page == "🔍 Market Scanner":
    st.title("🌍 True Market Scanner")
    st.sidebar.markdown("---")
    st.sidebar.header("Scanner Settings")
    
    strategy = st.sidebar.selectbox("1. Choose Strategy:", ["Custom (Manual)", "Insider Buying (Follow the Money)", "Oversold Quality (Dip Buying)", "Short Squeeze (High Risk/Reward)"])
    sort_criteria = st.sidebar.selectbox("2. Sort Market By:", ["Lowest P/E (Cheapest Earnings)", "Lowest P/B (Cheapest Assets)", "Worst Performance (Biggest Discount)"])
    
    sector_list = ["Any", "Basic Materials", "Communication Services", "Consumer Cyclical", "Consumer Defensive", "Energy", "Financial", "Healthcare", "Industrials", "Real Estate", "Technology", "Utilities"]
    sector_option = st.sidebar.selectbox("Sector", sector_list, index=0)
    mc_option = st.sidebar.selectbox("Market Cap", ["Any", "Micro ($50mln to $300mln)", "Small ($300mln to $2bln)", "Mid ($2bln to $10bln)", "Large ($10bln to $200bln)"], index=0)
    
    if strategy == "Custom (Manual)":
        pe_option = st.sidebar.selectbox("P/E Ratio", ["Any", "Under 15", "Under 20", "Under 30"], index=0)
        pb_option = st.sidebar.selectbox("Price/Book", ["Any", "Under 1", "Under 2", "Under 3"], index=0)
        debt_option = st.sidebar.selectbox("Debt/Equity", ["Any", "Under 0.5", "Under 1"], index=0)
    
    max_stocks = st.sidebar.slider("Max Stocks to Analyze", 5, 20, 10)

    if 'scan_results' not in st.session_state: st.session_state['scan_results'] = None

    if st.button("Run Scan", type="primary"):
        status = st.empty()
        status.info("Screening via Finviz...")
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
        if filters_dict: screener.set_filter(filters_dict=filters_dict)
        sort_map = {"Lowest P/E (Cheapest Earnings)": "Price/Earnings", "Lowest P/B (Cheapest Assets)": "Price/Book", "Worst Performance (Biggest Discount)": "Performance (Year)"}
        sort_key = sort_map.get(sort_criteria, 'Price/Earnings')

        try:
            df_results = screener.screener_view(order=sort_key)
            if not df_results.empty:
                enriched = []
                subset = df_results.head(max_stocks)
                progress = st.progress(0)
                for i, (idx, row) in enumerate(subset.iterrows()):
                    progress.progress((i+1)/len(subset))
                    disc_str = "-"
                    try:
                        tinfo = yf.Ticker(row['Ticker']).info
                        h52, curr = tinfo.get('fiftyTwoWeekHigh', 0), tinfo.get('currentPrice', float(row.get('Price', 0)))
                        if h52 > 0: disc_str = f"🔻 {((h52 - curr) / h52) * 100:.1f}%"
                    except: curr = float(row.get('Price', 0))
                    enriched.append({'Ticker': row['Ticker'], 'Price': curr, 'P/E': row.get('P/E', '-'), 'P/B': row.get('P/B', '-'), 'Discount_Str': disc_str})
                    time.sleep(0.1)
                st.session_state['scan_results'] = pd.DataFrame(enriched)
                status.success("Scan Complete!")
            else: st.session_state['scan_results'] = pd.DataFrame()
        except Exception as e: st.error(f"Error: {e}")

    if st.session_state['scan_results'] is not None and not st.session_state['scan_results'].empty:
        st.write("### Scan Results")
        h1, h2, h3, h4, h5, h6 = st.columns([1, 1, 1.5, 1, 1, 1])
        h1.markdown("**Ticker**"); h2.markdown("**Price**"); h3.markdown("**52W Discount**"); h4.markdown("**P/E**"); h5.markdown("**P/B**"); h6.markdown("**Action**")
        st.divider()
        for idx, row in st.session_state['scan_results'].iterrows():
            c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1.5, 1, 1, 1])
            c1.write(f"**{row['Ticker']}**"); c2.write(f"${row['Price']}"); c3.write(f"**{row['Discount_Str']}**"); c4.write(f"{row['P/E']}"); c5.write(f"{row['P/B']}")
            def add_callback(t, p):
                if save_to_portfolio(t, p): st.toast(f"✅ Saved {t}!")
                else: st.toast(f"⚠️ {t} already saved.")
            c6.button(f"Add", key=f"btn_{row['Ticker']}", on_click=add_callback, args=(row['Ticker'], row['Price']))
            st.divider()

# ==========================================
# PAGE: MY PORTFOLIO
# ==========================================
elif page == "📈 My Portfolio":
    st.title("📈 My Stock Tracker")
    df_p = load_portfolio()
    if df_p.empty: st.info("Portfolio empty.")
    else:
        if st.button("🔄 Refresh"): st.rerun()
        results = []
        for idx, row in df_p.iterrows():
            cur, w, m = get_performance_data(row['Ticker'])
            added = float(row['Price Added'])
            if added == 0: added = cur
            ret_abs = cur - added
            ret_pct = (ret_abs / added) * 100 if added > 0 else 0
            results.append({"Ticker": row['Ticker'], "Current Price": cur, "Cost Basis": added, "Gain/Loss $": ret_abs, "Gain/Loss %": ret_pct, "1 Week %": w, "1 Month %": m})
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
        to_rem = st.selectbox("Remove:", ["Select..."] + list(df_p['Ticker']))
        if st.button("Remove"):
            if to_rem != "Select...": remove_from_portfolio(to_rem); st.rerun()

# ==========================================
# PAGE: STOCK ANALYST
# ==========================================
elif page == "⚖️ Stock Analyst":
    st.title("⚖️ Comparative Analyst")
    st.write("Enter a ticker to see how it ranks against its sector peers.")
    
    target_ticker = st.text_input("Enter Ticker Symbol:", "").upper()
    
    if target_ticker:
        with st.spinner(f"Analyzing {target_ticker}..."):
            try:
                # 1. Fetch Target Stock Data
                stock = yf.Ticker(target_ticker)
                info = stock.info
                
                s_name = info.get('sector', 'Unknown')
                s_pe = info.get('trailingPE', 0)
                s_pb = info.get('priceToBook', 0)
                s_mc = info.get('marketCap', 0)
                s_price = info.get('currentPrice', 0)
                
                # --- PROFIT CHECK ---
                # Yahoo often returns None or 0 for P/E if profitable is False
                if s_pe is None: s_pe = 0
                
                if s_name == "Unknown":
                    st.error("Could not identify sector.")
                else:
                    st.subheader(f"Results for {target_ticker} ({s_name} Sector)")
                    
                    # 2. Get Sector Averages
                    screener = Valuation()
                    screener.set_filter(filters_dict={'Sector': s_name})
                    sector_df = screener.screener_view()
                    
                    sector_df['P/E'] = pd.to_numeric(sector_df['P/E'], errors='coerce')
                    sector_df['P/B'] = pd.to_numeric(sector_df['P/B'], errors='coerce')
                    
                    avg_pe = sector_df['P/E'].mean()
                    avg_pb = sector_df['P/B'].mean()
                    
                    # 3. Display Metrics (WITH FIX FOR 0 P/E)
                    m1, m2, m3 = st.columns(3)
                    
                    # P/E Logic: If 0, show "Unprofitable" instead of "Cheap"
                    if s_pe > 0:
                        pe_diff = ((s_pe - avg_pe) / avg_pe) * 100 if avg_pe > 0 else 0
                        m1.metric("P/E Ratio", f"{s_pe:.2f}", f"{pe_diff:.1f}% vs Sector", delta_color="inverse")
                    else:
                        m1.metric("P/E Ratio", "Unprofitable", "No Earnings", delta_color="off")
                    
                    # P/B Logic
                    pb_diff = ((s_pb - avg_pb) / avg_pb) * 100 if avg_pb > 0 else 0
                    m2.metric("P/B Ratio", f"{s_pb:.2f}", f"{pb_diff:.1f}% vs Sector", delta_color="inverse")
                    
                    m3.metric("Market Cap", f"${s_mc/1e9:.1f}B")
                    
                    # 4. Final Verdict
                    st.markdown("---")
                    st.write("### 📢 Value Verdict")
                    
                    reasons = []
                    score = 0
                    
                    # Score P/E (Only if profitable)
                    if s_pe > 0 and s_pe < avg_pe:
