import streamlit as st
import pandas as pd
from finvizfinance.screener.overview import Overview
import yfinance as yf
from textblob import TextBlob
import time
import subprocess
import sys

# --- 1. CONFIGURATION & SETUP ---
st.set_page_config(page_title="Deep Value Hunter", layout="wide")

# Fix for TextBlob on Streamlit Cloud
@st.cache_resource
def download_textblob_corpora():
    try:
        subprocess.check_call([sys.executable, "-m", "textblob.download_corpora"])
    except Exception as e:
        st.warning(f"Could not download TextBlob corpora: {e}")

download_textblob_corpora()

# --- 2. SIDEBAR WITH EXPLANATIONS ---
st.sidebar.title("🎛️ Screener Settings")
st.sidebar.markdown("Adjust these to filter the market.")

# -- MARKET CAP --
mc_help = "The total value of the company's shares. Large funds often ignore 'Small' and 'Micro' caps, which is where hidden value lives."
mc_option = st.sidebar.selectbox(
    "Market Cap (Size)", 
    ["Any", "Micro ($50mln to $300mln)", "Small ($300mln to $2bln)", "Mid ($2bln to $10bln)"], 
    index=2,
    help=mc_help
)

# -- P/E RATIO --
pe_help = "Price-to-Earnings Ratio. The lower the number, the cheaper the stock is relative to its profit. Under 15 is historically considered 'Value'."
pe_option = st.sidebar.selectbox(
    "P/E Ratio (Valuation)", 
    ["Any", "Under 10", "Under 15", "Under 20", "Under 30", "Under 50"], 
    index=2,
    help=pe_help
)

# -- P/B RATIO --
pb_help = "Price-to-Book Ratio. Compares stock price to the company's assets. Under 1.0 means you are paying less than the accounting value of their stuff."
pb_option = st.sidebar.selectbox(
    "Price/Book (Assets)", 
    ["Any", "Under 1", "Under 2", "Under 3", "Under 5"], 
    index=2,
    help=pb_help
)

# -- DEBT --
debt_help = "Debt-to-Equity Ratio. Measures financial leverage. Under 0.5 is very safe. Over 2.0 can be risky if rates rise."
debt_option = st.sidebar.selectbox(
    "Debt/Equity (Risk)", 
    ["Any", "Under 0.1", "Under 0.5", "Under 1"], 
    index=3,
    help=debt_help
)

# -- DIVIDEND --
div_help = "The % of cash the company pays back to you per year. > 3% is considered good income."
div_option = st.sidebar.selectbox(
    "Dividend Yield (Income)",
    ["Any", "Positive (>0%)", "High (>5%)", "Very High (>10%)"],
    index=0,
    help=div_help
)

# -- SHORT FLOAT --
short_help = "The % of shares that investors have bet AGAINST. High short interest (>20%) means everyone hates it... which can lead to a massive rally if good news comes out (Short Squeeze)."
short_option = st.sidebar.selectbox(
    "Float Short (Pessimism)",
    ["Any", "Low (<5%)", "High (>20%)", "Extreme (>30%)"],
    index=0,
    help=short_help
)

# --- 3. THE SCANNING FUNCTION ---
def get_hidden_value_stocks():
    status_text = st.empty() 
    status_text.info("🔍 Connecting to Finviz to screen stocks...")
    
    # Construct filters dynamically
    # IMPORTANT: If "Any" is selected, we simply DO NOT include that key in the dictionary.
    filters_dict = {}
    
    # Always ensure they are profitable (unless you want to find broken companies)
    # You can comment this out if you want to find money-losing turnaround plays
    filters_dict['Net Profit Margin'] = 'Positive (>0%)' 

    if mc_option != "Any":
        filters_dict['Market Cap.'] = mc_option
    if pe_option != "Any":
        filters_dict['P/E'] = pe_option
    if pb_option != "Any":
        filters_dict['P/B'] = pb_option
    if debt_option != "Any":
        filters_dict['Debt/Equity'] = debt_option
    if div_option != "Any":
        filters_dict['Dividend Yield'] = div_option
    if short_option != "Any":
        filters_dict['Float Short'] = short_option
    
    foverview = Overview()
    
    try:
        foverview.set_filter(filters_dict=filters_dict)
        df_results = foverview.screener_view()
        
        if df_results.empty:
            return None
            
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

    status_text.info(f"✅ Found {len(df_results)} candidates. Analyzing top results...")
    
    # Progress bar
    progress_bar = st.progress(0)
    total_stocks = len(df_results)
    
    results_data = []
    
    # Limit to top 15 stocks to save time/resources
    # Finviz puts the "best" matches first usually
    max_analyze = 15
    if total_stocks > max_analyze:
        st.toast(f"Analyzing top {max_analyze} of {total_stocks} stocks...")
        df_scan = df_results.head(max_analyze)
    else:
        df_scan = df_results

    # Iterate through results
    for index, row in df_scan.iterrows():
        symbol = row['Ticker']
        progress_bar.progress((index + 1) / len(df_scan))
        
        try:
            # Fetch news via yfinance
            stock = yf.Ticker(symbol)
            news = stock.news
            
            sentiment_score = 0
            news_count = 0
            
            if news:
                for article in news[:5]: 
                    title = article.get('title', '')
                    analysis = TextBlob(title)
                    sentiment_score += analysis.sentiment.polarity
                    news_count += 1
                
                if news_count > 0:
                    avg_sentiment = sentiment_score / news_count
                else:
                    avg_sentiment = 0
            else:
                avg_sentiment = 0 

            # Interpret Sentiment
            if news_count == 0:
                note = "Silent (Hidden?)"
            elif avg_sentiment < -0.1:
                note = "Hated (Contrarian)"
            elif avg_sentiment > 0.2:
                note = "Loved (Momentum)"
            else:
                note = "Neutral"

            results_data.append({
                'Ticker': symbol,
                'Company': row['Company'],
                'Sector': row['Sector'],
                'Price': row['Price'],
                'P/E': row['P/E'],
                'P/B': row['P/B'],
                'Sentiment': round(avg_sentiment, 2),
                'Note': note
            })
            
            time.sleep(0.1)
            
        except Exception as e:
            continue 

    status_text.empty() 
    progress_bar.empty() 
    
    # Create Final DataFrame
    final_df = pd.DataFrame(results_data)
    if not final_df.empty:
        # Sort by P/B (Value)
        final_df = final_df.sort_values(by='P/B', ascending=True)
        
    return final_df

# --- 4. THE APP UI ---
st.title("💰 Deep Value Hunter")
st.markdown("""
This tool finds stocks that are mathematically cheap but potentially ignored. 
**Hover over the (?) in the sidebar to understand the filters.**
""")

if st.button("Run Market Scan"):
    with st.spinner('Scanning the market...'):
        df = get_hidden_value_stocks()
        
        if df is not None and not df.empty:
            st.success(f"Scan Complete! Found {len(df)} stocks.")
            st.dataframe(
                df, 
                column_config={
                    "Ticker": "Symbol",
                    "P/B": st.column_config.NumberColumn("Price/Book", format="%.2f"),
                    "P/E": st.column_config.NumberColumn("P/E Ratio", format="%.2f"),
                    "Sentiment": st.column_config.NumberColumn("Sentiment Score", format="%.2f"),
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("No stocks matched. Try setting more filters to 'Any'.")
