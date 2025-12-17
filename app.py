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

# --- 2. THE SCANNING FUNCTION ---
def get_hidden_value_stocks():
    status_text = st.empty() 
    status_text.info("🔍 Connecting to Finviz to screen stocks...")
    
    # --- FIXED FILTERS (UPDATED FOR EXACT STRING MATCH) ---
    filters_dict = {
        'Market Cap.': 'Small ($300mln to $2bln)',
        'P/B': 'Under 1',
        'P/E': 'Under 15',
        'Debt/Equity': 'Under 0.5',
        'Net Profit Margin': 'Positive (>0%)'  # <--- UPDATED THIS LINE
    }
    
    foverview = Overview()
    
    try:
        foverview.set_filter(filters_dict=filters_dict)
        df_results = foverview.screener_view()
        
        if df_results.empty:
            return None
            
    except Exception as e:
        st.error(f"Error fetching data from Finviz: {e}")
        return None

    status_text.info(f"✅ Found {len(df_results)} candidates. Analyzing News Sentiment (this takes a moment)...")
    
    # Progress bar
    progress_bar = st.progress(0)
    total_stocks = len(df_results)
    
    results_data = []
    
    # Iterate through results
    for index, row in df_results.iterrows():
        symbol = row['Ticker']
        
        # Update progress
        progress_bar.progress((index + 1) / total_stocks)
        
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
                note = "Unknown/Ignored (Hidden Gem?)"
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
            
            # Tiny sleep to be polite to the API
            time.sleep(0.2)
            
        except Exception as e:
            continue # Skip this stock if error

    status_text.empty() # Clear the status text
    progress_bar.empty() # Clear progress bar
    
    # Create Final DataFrame
    final_df = pd.DataFrame(results_data)
    if not final_df.empty:
        # Sort by Price to Book (Deepest value first)
        final_df = final_df.sort_values(by='P/B', ascending=True)
        
    return final_df

# --- 3. THE APP UI ---
st.title("💰 Hidden Value Stock Finder")
st.markdown("""
This tool finds small-cap stocks that are:
*   **Cheap** (P/E < 15, P/B < 1)
*   **Safe** (Debt/Eq < 0.5)
*   **Profitable** (Positive Margins)
*   **Ignored** (Analyzed via News Sentiment)
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
            st.warning("No stocks matched these strict criteria today.")
