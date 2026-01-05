#!/usr/bin/env python3
"""
Fetch stock price history and valuation metrics from Yahoo Finance
"""

import yfinance as yf
import json
import sys
import time
from datetime import datetime, timedelta

# CUSIP to Ticker mapping (common stocks)
# This is a simplified mapping - in production, use a comprehensive CUSIP database
CUSIP_TO_TICKER = {
    '037833100': 'AAPL',  # Apple Inc.
    '02079K305': 'GOOGL', # Alphabet Inc.
    '594918104': 'MSFT',  # Microsoft Corp.
    '17275R102': 'CSCO',  # Cisco Systems Inc.
    '30303M102': 'META',  # Meta Platforms Inc.
    '88160R101': 'TSLA',  # Tesla Inc.
    '01609W102': 'BABA',  # Alibaba Group
    '91324P102': 'UNH',   # UnitedHealth Group
    '67066G104': 'NVDA',  # NVIDIA Corp.
    '46625H100': 'JPM',   # JPMorgan Chase & Co.
}

def cusip_to_ticker(cusip):
    """Convert CUSIP to ticker symbol"""
    # Try direct mapping first
    if cusip in CUSIP_TO_TICKER:
        return CUSIP_TO_TICKER[cusip]

    # TODO: Use OpenFIGI API or other service for lookup
    # For now, return None if not in our mapping
    return None

def fetch_stock_data(ticker, days=365):
    """
    Fetch stock price history and valuation metrics

    Args:
        ticker: Stock ticker symbol
        days: Number of days of historical data (default 365)

    Returns:
        dict: Stock data with price history and valuation metrics
    """
    print(f"Fetching data for {ticker}...")

    try:
        stock = yf.Ticker(ticker)

        # Fetch 1 year price history
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        history = stock.history(start=start_date, end=end_date)

        if history.empty:
            print(f"Warning: No price history found for {ticker}")
            return None

        # Convert price history to list of dicts
        price_history = []
        for date, row in history.iterrows():
            price_history.append({
                'date': date.strftime('%Y-%m-%d'),
                'close': round(float(row['Close']), 2)
            })

        # Fetch valuation metrics
        info = stock.info

        valuation_metrics = {
            'peRatio': info.get('trailingPE'),
            'pbRatio': info.get('priceToBook'),
            'psRatio': info.get('priceToSalesTrailing12Months'),
            'evToEbitda': info.get('enterpriseToEbitda'),
            'marketCap': info.get('marketCap', 0),
            'lastUpdated': datetime.now().isoformat()
        }

        print(f"Successfully fetched data for {ticker}")
        print(f"  Price points: {len(price_history)}")
        print(f"  P/E: {valuation_metrics['peRatio']}")
        print(f"  P/B: {valuation_metrics['pbRatio']}")

        return {
            'ticker': ticker,
            'priceHistory': price_history,
            'valuationMetrics': valuation_metrics
        }

    except Exception as e:
        print(f"Error fetching data for {ticker}: {str(e)}")
        return None

def enrich_fund_top_holdings(fund_top_holdings):
    """
    Enrich fund top holdings with stock data

    Args:
        fund_top_holdings: List of fund top holdings with CUSIP

    Returns:
        list: Enriched fund top holdings
    """
    print("\n=== Enriching top holdings with stock data ===\n")

    enriched_holdings = []
    ticker_cache = {}  # Cache to avoid duplicate API calls for same ticker

    for fund_holding in fund_top_holdings:
        cusip = fund_holding['topHolding']['cusip']
        company_name = fund_holding['topHolding']['companyName']

        # Try to get ticker from CUSIP
        ticker = cusip_to_ticker(cusip)

        if not ticker:
            print(f"Warning: Could not map CUSIP {cusip} ({company_name}) to ticker")
            # Use placeholder data
            fund_holding['topHolding']['ticker'] = 'N/A'
            fund_holding['topHolding']['priceHistory'] = []
            fund_holding['topHolding']['valuationMetrics'] = {
                'peRatio': None,
                'pbRatio': None,
                'psRatio': None,
                'evToEbitda': None,
                'marketCap': 0,
                'lastUpdated': datetime.now().isoformat()
            }
            enriched_holdings.append(fund_holding)
            continue

        # Check cache first
        if ticker in ticker_cache:
            print(f"Using cached data for {ticker}")
            stock_data = ticker_cache[ticker]
        else:
            # Fetch stock data
            stock_data = fetch_stock_data(ticker)

            if stock_data:
                ticker_cache[ticker] = stock_data
                # Rate limiting
                time.sleep(0.5)
            else:
                print(f"Failed to fetch data for {ticker}, using placeholder")
                stock_data = {
                    'ticker': ticker,
                    'priceHistory': [],
                    'valuationMetrics': {
                        'peRatio': None,
                        'pbRatio': None,
                        'psRatio': None,
                        'evToEbitda': None,
                        'marketCap': 0,
                        'lastUpdated': datetime.now().isoformat()
                    }
                }

        # Enrich the holding
        fund_holding['topHolding']['ticker'] = stock_data['ticker']
        fund_holding['topHolding']['priceHistory'] = stock_data['priceHistory']
        fund_holding['topHolding']['valuationMetrics'] = stock_data['valuationMetrics']

        enriched_holdings.append(fund_holding)

    print(f"\n=== Enriched {len(enriched_holdings)} holdings ===\n")

    return enriched_holdings

if __name__ == '__main__':
    # Read input JSON from stdin
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        with open(input_file, 'r') as f:
            fund_top_holdings = json.load(f)
    else:
        fund_top_holdings = json.load(sys.stdin)

    # Enrich with stock data
    enriched = enrich_fund_top_holdings(fund_top_holdings)

    # Output to stdout
    print(json.dumps(enriched, indent=2))
