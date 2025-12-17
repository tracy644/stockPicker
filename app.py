import streamlit as st
import pandas as pd
from finvizfinance.screener.overview import Overview
import yfinance as yf
from textblob import TextBlob
import time
import subprocess
import sys

# --- 1. CONFIGURATION & SETUP ---
st.set_page_config(page_title="Hidden Value Finder", layout="wide")

# Fix for TextBlob on Streamlit Cloud
@st.cache_resource
def download_textblob_corpora():
    try:
        subprocess.check_call([sys.executable, "-m", "textblob.download_corpora"])
    except Exception as e:
        st.warning(f"Could not download TextBlob corpora: {e}")

download_textblob_corpora()

# --- 2. SIDEBAR CONTROLS ---
st.sidebar.header("🔍 Filter Settings")
st.sidebar.write("Relax these if you see 0 results.")

# User selects filters (We map these to Finviz text)
mc_option = st.sidebar.selectbox("Market Cap", ["Small ($300mln to $2bln)", "Micro ($50mln to $300mln)", "Mid ($2bln to $10bln)", "Any"], index=0)
pb_option = st.sidebar.selectbox("Price/Book (Assets)", ["Under 1", "Under 2", "Under 3", "Any"], index=1) # Default to Under 2 (Looser)
pe_option = st.sidebar.selectbox("P/E Ratio (Earnings)", ["Under 15", "Under 20", "Under 25", "Under 30", "Any"], index=1) # Default to Under 20
debt_option = st.sidebar.selectbox("Debt/Equity", ["Under 0.5", "Under 1", "Any"], index=1) # Default to Under 1

# --- 3. THE SCANNING FUNCTION ---
def get_hidden_value_stocks():
    status_text = st.empty() 
    status_text.info("🔍 Connecting to Finviz to screen stocks...")
    
    # Construct filters dynamically based on Sidebar
    filters_dict = {
        'Net Profit Margin': 'Positive (>0%)' # Always keep this on (we don't want money losers)
    }

    # Only add filters if they are not 'Any'
    if mc_option != "Any":
        filters_dict['Market Cap.'] = mc_option
    if pb_option != "Any":
        filters_dict['P/B'] = pb_option
    if pe_option != "Any":
        filters_dict['P/E'] = pe_option
    if debt_option != "Any":
        filters_dict['Debt/Equity'] = debt_option
    
    foverview = Overview()
    
    try:
        foverview.set_filter(filters_dict=filters_dict)
        df_results = foverview.screener_view()
        
        if df_results.empty:
            return None
            
    except Exception as e:
        st.error(f"Error fetching data from Finviz: {e}")
        return None

    status_text.info(f"✅ Found {len(df_results)} candidates. Analyzing News Sentiment...")
    
    # Progress bar
    progress_bar = st.progress(0)
    total_stocks = len(df_results)
    
    results_data = []
    
    # Limit to top 10 stocks to save time if list is huge
    max_analyze = 10
    if total_stocks > max_analyze:
        st.toast(f"Analyzing top {max_analyze} of {total_stocks} stocks to save time...")
        df_scan = df_results.head(max_analyze)
    else:
        df_scan = df_results

    # Iterate through results
    for index, row in df_scan.iterrows():
        symbol = row['Ticker']
        
        # Update progress
        progress_bar.progress((index + 1) / len(df_scan))
        
        try:
            # Fetch news via yfinance
            stock = yf.Ticker(symbol)
            news = stock.news
            
            sentiment_score = 0
            news_count = 0
            
            if news:
                # Analyze up to 5 latest articles
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

            # Create the note
            note = ""
            if news_count == 0:
                note = "Unknown (Hidden Gem?)"
            elif avg_sentiment < -0.1:
                note = "Negative (Contrarian?)"
            elif avg_sentiment > 0.3:
                note = "Positive (Momentum)"
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
            
            # Tiny sleep
            time.sleep(0.1)
            
        except Exception as e:
            continue 

    status_text.empty() 
    progress_bar.empty() 
    
    # Create Final DataFrame
    final_df = pd.DataFrame(results_data)
    if not final_df.empty:
        final_df = final_df.sort_values(by='P/B', ascending=True)
        
    return final_df

# --- 4. THE APP UI ---
st.title("💰 Hidden Value Stock Finder")
st.markdown("""
**How to use:**
1. Use the **Sidebar (left)** to adjust strictness.
2. If you get 0 results, change **Price/Book** to "Under 2" or **Debt** to "Any".
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
            st.warning("No stocks matched these criteria. Try relaxing the filters in the Sidebar!")
