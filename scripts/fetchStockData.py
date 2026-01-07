#!/usr/bin/env python3
"""
Fetch stock price history and valuation metrics from Yahoo Finance
"""

import yfinance as yf
import json
import sys
from datetime import datetime, timedelta

# CUSIP to Ticker mapping (common stocks)
CUSIP_TO_TICKER = {
    '037833100': 'AAPL',  # Apple Inc.
    '02079K107': 'GOOGL', # Alphabet Inc. Class A
    '02079K305': 'GOOG',  # Alphabet Inc. Class C
    '594918104': 'MSFT',  # Microsoft Corp.
    '17275R102': 'CSCO',  # Cisco Systems Inc.
    '30303M102': 'META',  # Meta Platforms Inc.
    '88160R101': 'TSLA',  # Tesla Inc.
    '01609W102': 'BABA',  # Alibaba Group
    '91324P102': 'UNH',   # UnitedHealth Group
    '67066G104': 'NVDA',  # NVIDIA Corp.
    '46625H100': 'JPM',   # JPMorgan Chase & Co.
    '025816109': 'AXP',   # American Express Co.
    '023135106': 'AMZN',  # Amazon.com Inc.
    '060505104': 'BAC',   # Bank of America Corp.
    '191216100': 'KO',    # Coca-Cola Co.
    '166764100': 'CVX',   # Chevron Corp.
    '11135F101': 'AVGO',  # Broadcom Inc.
    '084670702': 'BRK.B', # Berkshire Hathaway Inc. Class B
    '68389X105': 'ORCL',  # Oracle Corp.
    '093712107': 'BE',    # Bloom Energy Corp.
    '722304102': 'PDD',   # PDD Holdings Inc.
    '02376R102': 'AMGN',  # Amgen Inc.
    '084664107': 'BK',    # Bank of New York Mellon Corp.
    '464287200': 'IEP',   # Icahn Enterprises L.P.
    '464287812': 'IEP',   # Icahn Enterprises L.P.
    '902494103': 'UBER',  # Uber Technologies Inc.
    '45780R107': 'IWM',   # iShares Russell 2000 ETF
    '464287838': 'IVV',   # iShares Core S&P 500 ETF
    '464287655': 'IWF',   # iShares Russell 1000 Growth ETF
    '78462F103': 'SPY',   # SPDR S&P 500 ETF Trust
}

def cusip_to_ticker(cusip):
    """Convert CUSIP to ticker symbol"""
    return CUSIP_TO_TICKER.get(cusip)

def fetch_stock_data(ticker, days=90):
    """Fetch stock price history and valuation metrics"""
    print(f"Fetching data for {ticker}...", file=sys.stderr)

    try:
        stock = yf.Ticker(ticker)

        # Fetch 1 year price history
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        history = stock.history(start=start_date, end=end_date)

        if history.empty:
            print(f"Warning: No price history found for {ticker}", file=sys.stderr)
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

        print(f"✓ Fetched {ticker}: {len(price_history)} points, P/E={valuation_metrics['peRatio']}", file=sys.stderr)

        return {
            'ticker': ticker,
            'priceHistory': price_history,
            'valuationMetrics': valuation_metrics
        }

    except Exception as e:
        print(f"Error fetching {ticker}: {str(e)}", file=sys.stderr)
        return None

def enrich_fund_top_holdings(fund_top_holdings):
    """Enrich fund top holdings with stock data"""
    print("\n=== Enriching holdings ===\n", file=sys.stderr)

    enriched_holdings = []
    ticker_cache = {}

    for fund_holding in fund_top_holdings:
        cusip = fund_holding['mostPurchased']['cusip']
        company_name = fund_holding['mostPurchased']['companyName']

        # Try to get ticker from CUSIP
        ticker = cusip_to_ticker(cusip)

        if not ticker:
            print(f"No ticker mapping for CUSIP {cusip} ({company_name})", file=sys.stderr)
            enriched_holdings.append(fund_holding)
            continue

        # Check cache first
        if ticker in ticker_cache:
            stock_data = ticker_cache[ticker]
        else:
            stock_data = fetch_stock_data(ticker)
            if stock_data:
                ticker_cache[ticker] = stock_data

        if stock_data:
            fund_holding['mostPurchased']['ticker'] = stock_data['ticker']
            fund_holding['mostPurchased']['priceHistory'] = stock_data['priceHistory']
            fund_holding['mostPurchased']['valuationMetrics'] = stock_data['valuationMetrics']

        enriched_holdings.append(fund_holding)

    print(f"\n✓ Enriched {len(enriched_holdings)} holdings\n", file=sys.stderr)
    return enriched_holdings

if __name__ == '__main__':
    # Read input JSON from stdin
    fund_top_holdings = json.load(sys.stdin)

    # Enrich with stock data
    enriched = enrich_fund_top_holdings(fund_top_holdings)

    # Output JSON to stdout (ONLY stdout, all logs to stderr)
    print(json.dumps(enriched, indent=2))
