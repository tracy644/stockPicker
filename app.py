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
        price_float = float(current_price)
    except:
        price_float = 0.0
        
    if ticker not in df['Ticker'].values:
        new_row = pd.DataFrame({
            'Ticker': [ticker], 
            'Date Added': [datetime.now().strftime("%Y-%m-%d")],
            'Price Added': [price_float]
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
    stock = yf.Ticker(ticker)
    current_price = 0.0
    change_1w = 0.0
    change_1m = 0.0
    
    try:
        current_price = stock.fast_info['last_price']
        
        hist = stock.history(period="2mo")
        if not hist.empty:
            week_ago = datetime.now() - timedelta(days=7)
            week_idx = hist.index.get_indexer([week_ago], method='nearest')[0]
            price_1w = hist['Close'].iloc[week_idx]
            
            month_ago = datetime.now() - timedelta(days=30)
            month_idx = hist.index.get_indexer([month_ago], method='nearest')[0]
            price_1m = hist['Close'].iloc[month_idx]

            if price_1w > 0:
                change_1w = ((current_price - price_1w) / price_1w) * 100
            if price_1m > 0:
                change_1m = ((current_price - price_1m) / price_1m) * 100
    except:
        pass
        
    return current_price, change_1w, change_1m

def get_stock_data_safe(ticker):
    """Fetches comprehensive stock info safely."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        name = info.get('longName', info.get('shortName', ticker))
        
        # --- CALCULATE ADVANCED METRICS ---
        
        # 1. Net Debt / EBITDA
        total_debt = info.get('totalDebt', 0)
        total_cash = info.get('totalCash', 0)
        ebitda = info.get('ebitda', 0)
        
        if ebitda and ebitda > 0:
            net_debt = total_debt - total_cash
            debt_ebitda = net_debt / ebitda
        else:
            debt_ebitda = 0 # N/A
            
        # 2. EV / FCF
        ev = info.get('enterpriseValue', 0)
        fcf = info.get('freeCashFlow', 0)
        
        if fcf and fcf > 0:
            ev_fcf = ev / fcf
        else:
            ev_fcf = 0 # N/A or Negative Cash Flow
            
        data = {
            'ticker': ticker,
            'name': name,
            'price': info.get('currentPrice', 0),
            'sector': info.get('sector', 'Unknown'),
            'pe': info.get('trailingPE', 0),
            'pb': info.get('priceToBook', 0),
            'mc': info.get('marketCap', 0),
            # NEW METRICS
            'revenue_growth': info.get('revenueGrowth', 0), # Percentage
            'operating_margin': info.get('operatingMargins', 0), # Percentage
            'debt_ebitda': debt_ebitda,
            'ev_fcf': ev_fcf
        }
        
        # Clean Nones
        for k, v in data.items():
            if v is None: data[k] = 0
            
        return data
    except:
        return None

def get_sector_averages(sector_name):
    """Fetches average P/E and P/B for a sector via Finviz."""
    try:
        screener = Valuation()
        screener.set_filter(filters_dict={'Sector': sector_name})
        sector_df = screener.screener_view()
        
        sector_df['P/E'] = pd.to_numeric(sector_df['P/E'], errors='coerce')
        sector_df['P/B'] = pd.to_numeric(sector_df['P/B'], errors='coerce')
        
        return sector_df['P/E'].mean(), sector_df['P/B'].mean()
    except:
        return 0, 0

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

    if 'scan_results' not in st.session_state:
        st.session_state['scan_results'] = None

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
                enriched_data = []
                subset = df_results.head(max_stocks)
                progress = st.progress(0)
                
                for i, (idx, row) in enumerate(subset.iterrows()):
                    progress.progress((i+1)/len(subset))
                    
                    discount_str = "-"
                    current_price = float(row.get('Price', 0))
                    
                    try:
                        tinfo = yf.Ticker(row['Ticker']).info
                        high_52 = tinfo.get('fiftyTwoWeekHigh', 0)
                        current_price = tinfo.get('currentPrice', current_price)
                        
                        if high_52 > 0:
                            disc_val = ((high_52 - current_price) / high_52) * 100
                            discount_str = f"🔻 {disc_val:.1f}%"
                    except:
                        pass
                    
                    enriched_data.append({
                        'Ticker': row['Ticker'],
                        'Price': current_price,
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
            st.error(f"Error: {e}")

    if st.session_state['scan_results'] is not None and not st.session_state['scan_results'].empty:
        st.write("### Scan Results")
        h1, h2, h3, h4, h5, h6 = st.columns([1, 1, 1.5, 1, 1, 1])
        h1.markdown("**Ticker**")
        h2.markdown("**Price**")
        h3.markdown("**52W Discount**")
        h4.markdown("**P/E**")
        h5.markdown("**P/B**")
        h6.markdown("**Action**")
        st.divider()
        
        for idx, row in st.session_state['scan_results'].iterrows():
            c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1.5, 1, 1, 1])
            c1.write(f"**{row['Ticker']}**")
            c2.write(f"${row['Price']}")
            c3.write(f"**{row['Discount_Str']}**")
            c4.write(f"{row['P/E']}")
            c5.write(f"{row['P/B']}")
            
            def add_callback(t, p):
                if save_to_portfolio(t, p):
                    st.toast(f"✅ Saved {t}!")
                else:
                    st.toast(f"⚠️ {t} already saved.")
            
            c6.button(f"Add", key=f"btn_{row['Ticker']}", on_click=add_callback, args=(row['Ticker'], row['Price']))
            st.divider()

# ==========================================
# PAGE: MY PORTFOLIO
# ==========================================
elif page == "📈 My Portfolio":
    st.title("📈 My Stock Tracker")
    df_p = load_portfolio()
    
    if df_p.empty:
        st.info("Portfolio empty.")
    else:
        if st.button("🔄 Refresh"):
            st.rerun()
            
        results = []
        for idx, row in df_p.iterrows():
            cur, w, m = get_performance_data(row['Ticker'])
            
            try:
                added = float(row['Price Added'])
            except:
                added = 0.0
                
            if added == 0: added = cur
            
            ret_abs = cur - added
            ret_pct = (ret_abs / added) * 100 if added > 0 else 0
            
            results.append({
                "Ticker": row['Ticker'],
                "Current Price": cur,
                "Cost Basis": added,
                "Gain/Loss $": ret_abs,
                "Gain/Loss %": ret_pct,
                "1 Week %": w,
                "1 Month %": m
            })
            
        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
        
        to_rem = st.selectbox("Remove:", ["Select..."] + list(df_p['Ticker']))
        if st.button("Remove"):
            if to_rem != "Select...":
                remove_from_portfolio(to_rem)
                st.rerun()

# ==========================================
# PAGE: STOCK ANALYST (ADVANCED)
# ==========================================
elif page == "⚖️ Stock Analyst":
    st.title("⚖️ Pro Comparative Analyst")
    st.write("Head-to-Head Comparison with Advanced Metrics")
    
    c1, c2 = st.columns(2)
    with c1:
        ticker_a = st.text_input("Stock A (e.g. KO)", "").upper()
    with c2:
        ticker_b = st.text_input("Stock B (Optional, e.g. PEP)", "").upper()
    
    if st.button("Analyze & Compare", type="primary"):
        if not ticker_a:
            st.warning("Please enter at least Stock A.")
        else:
            tickers = [ticker_a]
            if ticker_b: tickers.append(ticker_b)
            
            stock_data = {}
            with st.spinner("Crunching Advanced Metrics (Cash Flow, Debt, Margins)..."):
                for t in tickers:
                    data = get_stock_data_safe(t)
                    if data:
                        stock_data[t] = data
                    else:
                        st.error(f"Could not find {t}")
            
            if stock_data:
                # --- COMPARISON MODE ---
                if len(stock_data) == 2:
                    da = stock_data[ticker_a]
                    db = stock_data[ticker_b]
                    
                    st.divider()
                    st.subheader(f"⚔️ Face-Off: {da['name']} vs {db['name']}")
                    
                    colA, colB = st.columns(2)
                    score_a, score_b = 0, 0
                    
                    with colA:
                        st.markdown(f"### {da['ticker']}")
                        st.write(f"Price: **${da['price']}**")
                        st.write(f"Sector: {da['sector']}")
                    with colB:
                        st.markdown(f"### {db['ticker']}")
                        st.write(f"Price: **${db['price']}**")
                        st.write(f"Sector: {db['sector']}")

                    st.markdown("---")
                    st.write("### 📊 Fundamental Breakdown")

                    # 1. VALUATION (P/E & P/B)
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.metric("P/E Ratio", f"{da['pe']:.2f}")
                    c3.metric("P/E Ratio", f"{db['pe']:.2f}")
                    if da['pe'] > 0 and db['pe'] > 0:
                        if da['pe'] < db['pe']: 
                            c2.success(f"👈 {da['ticker']} Cheaper")
                            score_a += 1
                        else: 
                            c2.success(f"{db['ticker']} Cheaper 👉")
                            score_b += 1
                    elif da['pe'] > 0: 
                        c2.success(f"👈 {da['ticker']} Profitable")
                        score_a += 1
                    elif db['pe'] > 0:
                        c2.success(f"{db['ticker']} Profitable 👉")
                        score_b += 1

                    st.divider()
                    
                    # 2. CASH FLOW (EV/FCF)
                    c1, c2, c3 = st.columns([2, 1, 2])
                    val_a = f"{da['ev_fcf']:.1f}x" if da['ev_fcf'] > 0 else "N/A"
                    val_b = f"{db['ev_fcf']:.1f}x" if db['db_fcf'] if 'db_fcf' in locals() else f"{db['ev_fcf']:.1f}x" if db['ev_fcf'] > 0 else "N/A"
                    
                    c1.metric("EV / Free Cash Flow", val_a, help="Lower is better. Measures price relative to real cash generated.")
                    c3.metric("EV / Free Cash Flow", val_b)
                    
                    if da['ev_fcf'] > 0 and db['ev_fcf'] > 0:
                        if da['ev_fcf'] < db['ev_fcf']:
                            c2.success(f"👈 Better Cash Value")
                            score_a += 1
                        else:
                            c2.success(f"Better Cash Value 👉")
                            score_b += 1
                    
                    st.divider()

                    # 3. GROWTH & MARGINS
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.metric("Revenue Growth", f"{da['revenue_growth']*100:.1f}%")
                    c3.metric("Revenue Growth", f"{db['revenue_growth']*100:.1f}%")
                    if da['revenue_growth'] > db['revenue_growth']:
                        c2.success(f"👈 Faster Growth")
                        score_a += 1
                    else:
                        c2.success(f"Faster Growth 👉")
                        score_b += 1
                        
                    st.write("")
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.metric("Operating Margin", f"{da['operating_margin']*100:.1f}%")
                    c3.metric("Operating Margin", f"{db['operating_margin']*100:.1f}%")
                    if da['operating_margin'] > db['operating_margin']:
                        c2.success(f"👈 More Efficient")
                        score_a += 1
                    else:
                        c2.success(f"More Efficient 👉")
                        score_b += 1
                        
                    st.divider()

                    # 4. SOLVENCY (DEBT/EBITDA)
                    c1, c2, c3 = st.columns([2, 1, 2])
                    c1.metric("Net Debt / EBITDA", f"{da['debt_ebitda']:.2f}", help="Lower is better. Under 3.0 is usually safe.")
                    c3.metric("Net Debt / EBITDA", f"{db['debt_ebitda']:.2f}")
                    
                    # Logic: Lower debt ratio is better
                    if da['debt_ebitda'] < db['debt_ebitda']:
                        c2.success(f"👈 Safer Balance Sheet")
                        score_a += 1
                    else:
                        c2.success(f"Safer Balance Sheet 👉")
                        score_b += 1

                    # WINNER DECLARATION
                    st.markdown("---")
                    st.write("### 🏆 Final Verdict")
                    if score_a > score_b:
                        st.balloons()
                        st.success(f"**WINNER: {da['name']} ({score_a} - {score_b})**")
                        st.write(f"{da['ticker']} wins on fundamentals.")
                    elif score_b > score_a:
                        st.balloons()
                        st.success(f"**WINNER: {db['name']} ({score_b} - {score_a})**")
                        st.write(f"{db['ticker']} wins on fundamentals.")
                    else:
                        st.warning("It's a Tie! Both companies have mixed strengths.")

                    # Add Buttons
                    c1, c2 = st.columns(2)
                    if c1.button(f"Add {ticker_a}"): save_to_portfolio(ticker_a, da['price']); st.toast("Saved!")
                    if c2.button(f"Add {ticker_b}"): save_to_portfolio(ticker_b, db['price']); st.toast("Saved!")

                # --- SINGLE STOCK MODE (Simple View) ---
                elif len(stock_data) == 1:
                    d = list(stock_data.values())[0]
                    st.subheader(f"Analysis: {d['name']}")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("P/E Ratio", f"{d['pe']:.2f}")
                    c2.metric("EV / Free Cash Flow", f"{d['ev_fcf']:.1f}x")
                    c3.metric("Net Debt / EBITDA", f"{d['debt_ebitda']:.2f}")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Revenue Growth", f"{d['revenue_growth']*100:.1f}%")
                    c2.metric("Operating Margin", f"{d['operating_margin']*100:.1f}%")
                    c3.metric("Market Cap", f"${d['mc']/1e9:.1f}B")
                    
                    st.write("---")
                    if st.button(f"Add {d['ticker']}"):
                        save_to_portfolio(d['ticker'], d['price'])
                        st.toast("Saved!")
