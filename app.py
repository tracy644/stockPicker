import pandas as pd
from finvizfinance.screener.overview import Overview
from finvizfinance.screener.valuation import Valuation
from finvizfinance.screener.financial import Financial
import yfinance as yf
from textblob import TextBlob
import time

def get_hidden_value_stocks():
    print("🔍 Scanning the market for hidden value stocks...")
    
    # 1. Setup the Screener Filters
    # We combine filters to find specific 'hidden' value characteristics
    filters_dict = {
        'Market Cap': 'Small ($300mln to $2bln)', # ignored by big wall street firms
        'P/B': 'Under 1',                         # Trading below "book" value
        'P/E': 'Under 15',                        # Cheap relative to earnings
        'Debt/Equity': 'Under 0.5',               # Low debt (safe)
        'Net Profit Margin': 'Positive'           # Must be actually making money
    }
    
    # Initialize the screener with our filters
    # We use 'Overview' to get the base list
    foverview = Overview()
    foverview.set_filter(filters_dict=filters_dict)
    
    # Get the results
    try:
        df_results = foverview.screener_view()
        if df_results.empty:
            print("No stocks matched the strict criteria.")
            return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

    print(f"Found {len(df_results)} potential candidates. Analyzing sentiment...")
    
    # 2. Analyze Sentiment for each candidate
    # We want to know if they are hated (contrarian) or just ignored.
    
    results_data = []
    
    for symbol in df_results['Ticker']:
        try:
            # Fetch recent news using yfinance
            stock = yf.Ticker(symbol)
            news = stock.news
            
            sentiment_score = 0
            news_count = 0
            
            if news:
                for article in news[:5]: # Analyze latest 5 articles
                    title = article.get('title', '')
                    # Simple sentiment analysis using TextBlob
                    analysis = TextBlob(title)
                    sentiment_score += analysis.sentiment.polarity
                    news_count += 1
                
                avg_sentiment = sentiment_score / news_count
            else:
                avg_sentiment = 0 # No news often means "ignored" (Good for hidden value!)

            # Add data to our list
            # We grab the row from our screener dataframe to keep the fundamental data
            row = df_results.loc[df_results['Ticker'] == symbol].iloc[0]
            
            results_data.append({
                'Ticker': symbol,
                'Company': row['Company'],
                'Sector': row['Sector'],
                'Price': row['Price'],
                'P/E': row['P/E'],
                'P/B': row['P/B'],
                'Sentiment': round(avg_sentiment, 2),
                'Note': interpret_sentiment(avg_sentiment, news_count)
            })
            
            # Sleep briefly to avoid hitting API rate limits too hard
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Skipping {symbol} due to error: {e}")
            continue

    # Create final DataFrame
    final_df = pd.DataFrame(results_data)
    
    # Sort by P/B ratio (Deepest value first)
    if not final_df.empty:
        final_df = final_df.sort_values(by='P/B', ascending=True)
        
    return final_df

def interpret_sentiment(score, count):
    if count == 0:
        return "Unknown/Ignored (Hidden Gem?)"
    elif score < -0.1:
        return "Negative (Contrarian Play?)"
    elif score > 0.3:
        return "Positive (Momentum?)"
    else:
        return "Neutral"

if __name__ == "__main__":
    value_stocks = get_hidden_value_stocks()
    
    if value_stocks is not None:
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        print("\n--- POTENTIAL HIDDEN VALUE STOCKS ---")
        print(value_stocks[['Ticker', 'Price', 'P/E', 'P/B', 'Sector', 'Sentiment', 'Note']].to_string(index=False))
        
        # Save to CSV
        value_stocks.to_csv('hidden_value_stocks.csv', index=False)
        print("\nResults saved to 'hidden_value_stocks.csv'")
