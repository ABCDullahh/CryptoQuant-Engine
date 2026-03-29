# Comprehensive Report: Free & Free-Tier Data Sources for Cryptocurrency Quantitative Trading

**Research Date:** February 10, 2026
**Purpose:** Identify all free and free-tier data sources for building a cryptocurrency quantitative trading system

---

## TABLE OF CONTENTS

1. [Exchange APIs (Free Real-time & Historical Data)](#1-exchange-apis)
2. [CCXT Library](#2-ccxt-library)
3. [Free Historical Data Downloads](#3-free-historical-data-downloads)
4. [Free/Free-Tier Market Data APIs](#4-free-market-data-apis)
5. [Free On-Chain Data](#5-free-on-chain-data)
6. [Free Sentiment Data](#6-free-sentiment-data)
7. [Free Technical Analysis Libraries](#7-free-technical-analysis-libraries)
8. [Free Derivatives Data](#8-free-derivatives-data)
9. [Free News/RSS Feeds](#9-free-news-rss-feeds)
10. [Free Backtesting & ML Tools](#10-free-backtesting-ml-tools)
11. [Free Infrastructure](#11-free-infrastructure)
12. [Free TradingView & Charting Data](#12-free-tradingview-charting)

---

## 1. EXCHANGE APIs (Free Real-time & Historical Data) <a name="1-exchange-apis"></a>

All major crypto exchanges provide FREE API access for market data. No paid tier is needed for price data, order books, trades, and OHLCV candles. The key constraint is rate limiting.

### 1.1 Binance API
- **URL:** https://developers.binance.com/docs/binance-spot-api-docs
- **Free Data:**
  - Real-time price via WebSocket (free, unlimited streaming)
  - Historical OHLCV klines (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M)
  - Order book depth (up to 5000 levels)
  - Recent trades & aggregate trades
  - Funding rates (USDT-M and COIN-M futures)
  - Open interest
  - Long/short ratios
- **Rate Limits:**
  - REST: 2,400 requests/min per IP (Spot); 2,400/min (Futures)
  - WebSocket: 300 connections per 5 minutes per IP
  - Klines: max 1,000 candles per request (default 500)
- **Historical Depth:** Data goes back to exchange launch (~2017 for major pairs). No time limit on how far back you can query; just paginate through 1000-candle blocks.
- **Bulk Download:** https://data.binance.vision/ provides FREE downloadable ZIP files of historical klines, trades, and aggTrades for spot, USDT-M futures, and COIN-M futures. Daily and monthly files. Goes back to exchange inception.
- **Gotchas:** Timestamps changed to microseconds for spot data from Jan 1, 2025 onwards. IP-based rate limiting means shared IPs (VPS) can be problematic.
- **Quality Rating:** 5/5 -- The gold standard for free crypto data.

### 1.2 Bybit API
- **URL:** https://bybit-exchange.github.io/docs/v5/
- **Free Data:**
  - Real-time WebSocket feeds (tickers, klines, orderbook, trades, liquidations)
  - Historical OHLCV (returns 200 candles per request by default)
  - Funding rates, open interest
  - Order book depth
- **Rate Limits:**
  - REST: 600 requests per 5 seconds per IP (120/sec effective)
  - WebSocket: Market data requests are NOT counted against rate limits
- **Historical Depth:** Historical data available since exchange launch. Bulk historical data downloads available at https://www.bybit.com/derivatives/en/history-data
- **Gotchas:** WebSocket is the preferred method for real-time data (free from rate limit counting).
- **Quality Rating:** 4.5/5

### 1.3 OKX API
- **URL:** https://www.okx.com/docs-v5/en/
- **Free Data:**
  - Complete market data (spot, futures, perpetuals, options)
  - Historical candlesticks (limit 300 for live, 100 for history per request)
  - Funding rates, open interest, long/short ratios
  - Order book, trades
  - WebSocket streaming
- **Rate Limits:**
  - Varies by endpoint; public endpoints are IP-rate-limited
  - Historical candles endpoint: 100 candles per request for deep history
- **Historical Depth:** "Recent years" of history available via API. OKX also offers a historical data marketplace at https://www.okx.com/en-us/historical-data
- **Gotchas:** History candle limit of 100 per request makes bulk historical collection slow. Consider using their data marketplace or Binance data.vision for bulk downloads.
- **Quality Rating:** 4/5

### 1.4 Coinbase (Advanced Trade API)
- **URL:** https://docs.cdp.coinbase.com/exchange/docs/
- **Free Data:**
  - Real-time WebSocket feeds
  - Historical candles
  - Order book (Level 2 and Level 3)
  - Trades
- **Rate Limits:**
  - Public: 3 requests/second (burst to 6/sec)
  - Private: 5 requests/second (burst to 10/sec)
- **Historical Depth:** Good history available for major pairs
- **Gotchas:** Lower rate limits than Binance. Fewer trading pairs (US-focused). No derivatives data.
- **Quality Rating:** 3.5/5

### 1.5 Kraken API
- **URL:** https://docs.kraken.com/api/
- **Free Data:**
  - OHLC historical data
  - Order book
  - Trades
  - WebSocket (free, does NOT count against REST rate limits)
  - Futures: funding rates, open interest
- **Rate Limits:**
  - Public: ~1 request/second sustained
  - Counter-based system: most calls +1, ledger/trade history +2
  - WebSocket subscription rate: 200/sec (standard), 500/sec (pro)
- **Historical Depth:** Established exchange with data going back to 2013 for BTC.
- **Gotchas:** Rate limits are more restrictive than Binance. Counter-based system can be confusing.
- **Quality Rating:** 4/5

### 1.6 KuCoin API
- **URL:** https://www.kucoin.com/docs-new/rate-limit
- **Free Data:**
  - Full market data suite (candles, order book, trades, tickers)
  - WebSocket streaming
- **Rate Limits:** Varies by endpoint; recently upgraded limits. Documented at their rate-limit page.
- **Historical Depth:** Data since exchange launch (~2017)
- **Gotchas:** Rate limit documentation requires careful reading per endpoint type.
- **Quality Rating:** 3.5/5

### 1.7 Gate.io API
- **URL:** https://www.gate.io/docs/apiv4/
- **Free Data:**
  - Spot and futures market data
  - Candles, order book, trades
  - Funding rates, open interest
- **Rate Limits:** 50 requests/second per channel
- **Quality Rating:** 3.5/5

### 1.8 MEXC API
- **URL:** https://www.mexc.com/mexc-api
- **Free Data:**
  - Market data for spot and futures
  - Candles, trades, order book
- **Rate Limits:** 5 orders/sec for trading; market data limits vary
- **Gotchas:** Lower rate limits than larger exchanges. Less documentation quality.
- **Quality Rating:** 3/5

### 1.9 Bitget API
- **URL:** https://www.bitget.com/api
- **Free Data:**
  - Full market data (spot, futures)
  - Funding rates, open interest
  - Excellent sandbox environment
- **Rate Limits:** Documented per endpoint
- **Gotchas:** Good sandbox for testing.
- **Quality Rating:** 3.5/5

---

## 2. CCXT LIBRARY <a name="2-ccxt-library"></a>

### CCXT (CryptoCurrency eXchange Trading Library)
- **URL:** https://github.com/ccxt/ccxt | https://docs.ccxt.com/
- **License:** MIT (fully free and open-source)
- **What It Provides:**
  - Unified interface to 100+ cryptocurrency exchanges
  - Public APIs accessible WITHOUT authentication (market data is free)
  - fetch_ohlcv(), fetch_order_book(), fetch_trades(), fetch_ticker(), fetch_funding_rate()
  - Automatic pagination and data normalization
- **Free Data Available:**
  - All public market data from any supported exchange
  - OHLCV candles, order books, trades, tickers
  - No API key needed for market data
- **Rate Limiting:**
  - Built-in rate limiter (Leaky Bucket algorithm)
  - `exchange.rateLimit` property set to safe defaults
  - Different endpoints rate-limited differently
  - Example: rateLimit=100 means 100ms between requests = 10 req/sec
- **Best Exchanges for CCXT Free Data:**
  1. **Binance** -- Best support, most data, highest limits
  2. **Bybit** -- Excellent v5 API support
  3. **OKX** -- Good data coverage
  4. **Kraken** -- Reliable, long history
  5. **KuCoin** -- Good altcoin coverage
- **CCXT Pro (Premium):** Paid version with WebSocket support. Cost ~$15/month for individual developers. The free CCXT version only supports REST API polling.
- **Gotchas:** Free version is REST-only (no WebSocket). Some exchanges have quirks that CCXT documents. Historical data pagination varies by exchange.
- **Quality Rating:** 5/5 -- Essential tool for any crypto quant system.

---

## 3. FREE HISTORICAL DATA DOWNLOADS <a name="3-free-historical-data-downloads"></a>

### 3.1 Binance Public Data (data.binance.vision)
- **URL:** https://data.binance.vision/
- **GitHub:** https://github.com/binance/binance-public-data
- **What's Free:**
  - Complete historical klines (candles) for ALL trading pairs
  - Aggregate trades, individual trades
  - Spot, USDT-Margined Futures, COIN-Margined Futures
  - Daily and monthly ZIP files with checksums
- **Resolutions Available:** 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
- **Historical Depth:** Back to exchange launch (2017 for early pairs)
- **Format:** CSV in ZIP files
- **Gotchas:** Spot timestamps switched to microseconds from Jan 2025. New daily data appears next day; new monthly data on first Monday of month.
- **Quality Rating:** 5/5 -- BEST free historical data source. Period.

### 3.2 CryptoDataDownload
- **URL:** https://www.cryptodatadownload.com/
- **What's Free:**
  - Instant CSV downloads, no registration required
  - Data from 20+ exchanges (Binance, Bitstamp, Gemini, Bitfinex, etc.)
  - 1000+ cryptocurrencies covered
  - Daily, Hourly, and Minute intervals
- **Historical Depth:** January 2019 through present (varies by exchange)
- **Format:** CSV
- **Gotchas:** Data coverage starts 2019 for most pairs (less deep than Binance data.vision). "Will never ask you to pay for raw historical data."
- **Quality Rating:** 4/5

### 3.3 Kaggle Crypto Datasets
- **URL:** https://www.kaggle.com/datasets?search=cryptocurrency
- **Notable Datasets:**
  - "Top 100 Cryptocurrencies Historical Dataset" (updated regularly)
  - "Bitcoin Historical Data" (minute-level from 2012)
  - "106 Cryptocurrency Historical Data" (daily OHLCV)
  - "Cryptocurrency Price History" (multi-coin daily)
  - "Crypto Fear and Greed Index" (daily)
- **What's Free:** All datasets free to download with Kaggle account
- **Format:** CSV
- **Gotchas:** Data may not be regularly updated. Quality varies by uploader. Best used as a starting point or for static backtests, not as a live data pipeline.
- **Quality Rating:** 3.5/5

### 3.4 Python Package: binance-historical-data
- **URL:** https://pypi.org/project/binance-historical-data/
- **What It Does:** Automates downloading from data.binance.vision with 3 lines of code
- **Supports:** Spot, USDT-M, COIN-M; klines, aggTrades, trades
- **Quality Rating:** 4/5

---

## 4. FREE/FREE-TIER MARKET DATA APIs <a name="4-free-market-data-apis"></a>

### 4.1 CoinGecko API
- **URL:** https://www.coingecko.com/en/api
- **Docs:** https://docs.coingecko.com/
- **Free Tiers:**
  - **Public API (no key):** 5-15 calls/min (variable by global load)
  - **Demo Plan (free, requires key):** 30 calls/min, 10,000 calls/month
- **Data Available (Free):**
  - Current prices for 10,000+ coins
  - Market cap, volume, price change percentages
  - OHLC candles (1/7/14/30/90/180/365 day ranges)
  - Historical market data
  - Exchange data, trending coins
  - Global DeFi data
- **Historical Depth:** Years of daily data; OHLC limited to predefined ranges
- **Gotchas:** Price data cached at 1-5 min intervals for free users. Monthly cap of 10K calls on Demo plan is limiting for high-frequency polling. No minute-level OHLCV.
- **Quality Rating:** 4/5 -- Excellent for portfolio tracking and overview data, NOT for trading signals.

### 4.2 CoinMarketCap API
- **URL:** https://coinmarketcap.com/api/
- **Pricing:** https://coinmarketcap.com/api/pricing/
- **Free Tier (Basic Plan):**
  - 10,000 credits/month (~333 calls/day)
  - 11 core endpoints
  - Current market data, rankings, listings
  - No time limit on free plan
- **Data Available:**
  - Latest cryptocurrency listings and quotes
  - Market pairs and exchange data
  - Global market metrics
- **NOT Included in Free:**
  - Historical data (paid only)
  - Advanced endpoints
- **Gotchas:** Credits are based on data points returned (1 credit per 100 data points), not raw API calls. No historical data on free tier is a major limitation.
- **Quality Rating:** 3/5 -- Good for current data only; useless for backtesting.

### 4.3 CryptoCompare API
- **URL:** https://www.cryptocompare.com/coins/guides/how-to-use-our-api/
- **Free Tier:**
  - ~100,000 calls/month (reported by users; exact limit not publicly stated)
  - Access to 60+ endpoints
  - Daily and hourly historical data (free)
  - Minute data: only last 7 days (beyond 7 days is enterprise-only)
- **Data Available:**
  - Price data (single, multi, historical)
  - OHLCV (daily, hourly, minute)
  - Social stats, mining data
  - Exchange data, order book
- **Gotchas:** Minute-level data beyond 7 days requires paid plan (~$80/mo+). Not ideal for minute-level backtesting. API key model required.
- **Quality Rating:** 3.5/5

### 4.4 CoinPaprika API
- **URL:** https://coinpaprika.com/api/
- **Pricing:** https://coinpaprika.com/api/pricing/
- **Free Tier:**
  - 2,500 available assets
  - 1 year of daily historical data
  - 25,000 calls/month
  - No credit card required
  - Personal/non-commercial use only
- **Data Available:**
  - Coin prices, market data
  - Exchanges, markets
  - Historical OHLCV (daily, 1 year)
  - Tags, people (team data)
- **Gotchas:** 1-year historical limit on free tier. Non-commercial restriction.
- **Quality Rating:** 3.5/5

### 4.5 CoinCap API 2.0
- **URL:** https://docs.coincap.io/
- **Free Tier:**
  - No API key: 200 requests/minute
  - With API key (free): 500 requests/minute
  - No monthly cap mentioned
- **Data Available:**
  - Real-time and historical cryptocurrency prices
  - Assets, markets, exchanges, candles, rates
  - RESTful + WebSocket
- **Gotchas:** Less comprehensive than CoinGecko for obscure altcoins. Data quality is generally good.
- **Quality Rating:** 4/5 -- Generous rate limits for a free API.

### 4.6 Messari API
- **URL:** https://messari.io/api
- **Docs:** https://docs.messari.io/
- **Free Tier:**
  - 20 requests/minute
  - Access to prices, market data, on-chain metrics, qualitative profiles
  - No API key needed for basic endpoints (but rate-limited)
- **Data Available:**
  - Asset metrics and profiles
  - Historical price data (OHLCV)
  - On-chain metrics (for supported assets)
  - Qualitative research data
- **Gotchas:** 20 req/min is quite low. No redistribution rights. Attribution required. Enterprise: $5,000/year.
- **Quality Rating:** 3/5

### 4.7 LiveCoinWatch API
- **URL:** https://www.livecoinwatch.com/tools/api
- **Docs:** https://livecoinwatch.github.io/lcw-api-docs/
- **Free Tier:**
  - Free price API with live data from top exchanges
  - Data collected directly from exchanges
- **Data Available:**
  - Real-time coin prices
  - Market overview data
  - Historical data
- **Quality Rating:** 3/5

### 4.8 Nomics API
- **URL:** https://nomics.com/docs
- **Status:** API appears still operational but company activity has diminished. Use with caution.
- **Free Tier:** Free API key for basic access to prices, market data, and exchange rates
- **Gotchas:** Uncertain long-term viability. Consider alternatives.
- **Quality Rating:** 2/5 (due to uncertain status)

---

## 5. FREE ON-CHAIN DATA <a name="5-free-on-chain-data"></a>

### 5.1 Glassnode (Free / Community Tier)
- **URL:** https://studio.glassnode.com/ | https://docs.glassnode.com/
- **Free Tier (Standard):**
  - Access to all "Basic" (Tier 1) metrics
  - 24-hour resolution only (daily granularity)
  - Limited to BTC and ETH for most metrics
  - Basic metrics include: active addresses, transaction count, transfer volume, exchange flows (basic), MVRV ratio (basic), NVT ratio (basic), supply metrics
- **NOT Free:**
  - Hourly/10-min resolution (Professional plan, ~$79/mo)
  - Advanced/Premium metrics (SOPR, Realized Price bands, Cohort analysis)
  - Full historical depth for some metrics
- **Gotchas:** Free tier is very limited compared to paid. Good for daily signals, not intraday. Many premium metrics are behind paywall.
- **Quality Rating:** 3/5 (free tier); 5/5 (paid)

### 5.2 DeFiLlama API
- **URL:** https://defillama.com/ | https://api-docs.defillama.com/
- **Free Tier:**
  - FULLY FREE open API for core data
  - No API key required for basic endpoints
  - Attribution appreciated but not strictly required
- **Data Available (Free):**
  - TVL (Total Value Locked) for all protocols and chains
  - Revenue and fees data
  - Token prices (current and historical)
  - DEX volume data
  - Yields/APY data
  - Stablecoin data
  - Protocol-level metrics
- **Rate Limits:** Not explicitly stated; rate limiting exists but is generous for normal use
- **Gotchas:** Some advanced endpoints require paid API plan. Premium endpoints marked with lock icon. Core TVL, prices, and protocol data are free.
- **Quality Rating:** 5/5 -- Best free DeFi data source available.

### 5.3 Etherscan API
- **URL:** https://etherscan.io/apis | https://docs.etherscan.io/
- **Free Tier:**
  - 5 calls/second, up to 100,000 calls/day
  - Full Ethereum blockchain data
  - Account balances, transaction lists
  - Token transfers (ERC-20, ERC-721, ERC-1155)
  - Contract ABIs and source code
  - Gas price oracle
  - Internal transactions
- **Recent Changes (Nov 2025):**
  - Free tier limited to ~90% of chains (some L2s removed: Avalanche, Base, BNB, OP)
  - Contract-related endpoints remain free across all chains
  - New discounted Lite plan for full chain coverage
- **Gotchas:** Historical endpoints limited to 2 calls/sec. Multi-chain coverage reduced on free tier. Etherscan API V2 now required.
- **Quality Rating:** 4/5 (for Ethereum-specific data)

### 5.4 BscScan API (DEPRECATED)
- **URL:** https://docs.bscscan.com/
- **Status:** BscScan APIs deprecated. Migrate to Etherscan API V2 or BSCTrace via MegaNode.
- **BSCTrace Alternative:** Free tier available for BNB Chain via MegaNode
- **Quality Rating:** 2/5 (due to deprecation)

### 5.5 Dune Analytics
- **URL:** https://dune.com/ | https://docs.dune.com/
- **Free Tier:**
  - 2,500 credits/month
  - Unlimited dashboards
  - API access included
  - SQL queries across 100+ blockchains
  - 60,000+ decoded contracts
  - 3+ petabytes of indexed data
- **Data Available:**
  - Raw blockchain data (transactions, logs, traces)
  - Decoded smart contract data
  - DEX trades, NFT activity, DeFi protocol data
  - Custom SQL queries on any indexed chain
- **Gotchas:** 2,500 monthly credits can be consumed quickly with complex queries. Query execution can be slow during peak hours on free tier. Learning SQL is required.
- **Quality Rating:** 4.5/5 -- Incredibly powerful for custom on-chain analysis.

### 5.6 Nansen
- **URL:** https://www.nansen.ai/
- **Free Tier:** NO free tier. Plans start at $100/month.
- **Quality Rating:** N/A for free users

### 5.7 IntoTheBlock / Sentora
- **URL:** https://sentora.com/analytics-research (formerly IntoTheBlock)
- **Free Tier:** IntoTheBlock has been sunset and relaunched as Sentora Research -- described as a free, research-first solution for decoding DeFi. 7-day free trial available (no credit card).
- **Gotchas:** Platform transition may affect data availability and API stability.
- **Quality Rating:** 3/5 (transitional state)

### 5.8 Santiment
- **URL:** https://santiment.net/ | https://app.santiment.net/pricing
- **Free Tier:**
  - Free-to-view basic charts and dashboards
  - Limited historical depth
  - Basic on-chain and social metrics
- **Paid Plans:** Starting at $49/month (payable in SAN tokens for discount)
- **Quality Rating:** 2.5/5 (free tier is very limited)

### 5.9 CryptoQuant
- **URL:** https://cryptoquant.com/
- **Free Tier:**
  - Feature-limited free plan
  - Delayed data (not real-time)
  - Basic exchange flow data
  - Limited chart access
- **Paid Plans:** Advanced $29/mo (annual), Professional $109/mo, Premium $799/mo
- **Quality Rating:** 2.5/5 (free tier is limited; paid is excellent)

### 5.10 Token Terminal
- **URL:** https://tokenterminal.com/
- **Free Tier:**
  - Free version provides basic protocol financial data
  - Fees, revenue, stablecoin supply metrics
  - Limited historical depth
- **Paid Plans:** PRO $350/mo, API $999/mo
- **Quality Rating:** 3/5 (free version is "enough for most investors")

---

## 6. FREE SENTIMENT DATA <a name="6-free-sentiment-data"></a>

### 6.1 Alternative.me Fear & Greed Index
- **URL:** https://alternative.me/crypto/fear-and-greed-index/
- **API:** https://api.alternative.me/fng/?limit=0
- **Free Tier:**
  - COMPLETELY FREE, forever
  - 60 requests/minute (10-min rolling window)
  - Full historical data available
  - JSON format
- **Data Available:**
  - Daily Fear & Greed Index (0-100 scale)
  - Historical values going back years
  - Classification labels (Extreme Fear, Fear, Neutral, Greed, Extreme Greed)
- **Gotchas:** Only updates once daily. Single metric (no granular breakdown). Bitcoin-centric.
- **Quality Rating:** 5/5 -- Simple, reliable, completely free.

### 6.2 Reddit API (via PRAW)
- **URL:** https://www.reddit.com/dev/api/
- **PRAW:** https://praw.readthedocs.io/
- **Free Tier:**
  - OAuth authenticated: 100 requests/minute (some sources say 60/min)
  - Unauthenticated: 10 requests/minute
  - Free for personal scripts and bots
- **Data Available:**
  - Subreddit posts and comments (r/cryptocurrency, r/bitcoin, r/ethtrader, etc.)
  - Upvotes, comment counts, post frequency
  - User activity metrics
- **Gotchas:** Reddit tightened API access in 2023-2024. Pre-approval now required for some use cases. Rate limits enforced strictly. PRAW handles rate limiting automatically via X-Ratelimit headers. Historical data access is limited (Reddit search only goes back ~6 months reliably).
- **Quality Rating:** 3.5/5

### 6.3 Twitter/X API
- **URL:** https://developer.twitter.com/
- **Free Tier:**
  - WRITE-ONLY access (can post ~1,500 tweets/month)
  - NO read access on free tier
  - Cannot retrieve tweets for sentiment analysis
- **Basic Plan:** $200/month for minimal read access
- **Enterprise:** $42,000/month
- **Gotchas:** FREE TIER IS USELESS for sentiment analysis. You cannot read tweets on the free plan. This is a major change from pre-2023.
- **Quality Rating:** 0/5 for free tier (no read access = no sentiment data)

### 6.4 CryptoPanic API
- **URL:** https://cryptopanic.com/developers/api/
- **Free Tier:**
  - Free API auth token available
  - Access to aggregated crypto news from multiple sources
  - Filtering by currency, kind (news/media), region
- **Data Available:**
  - News articles with sentiment indicators (bullish/bearish/neutral)
  - Source attribution
  - Currency tags
- **Gotchas:** Free tier has limited features compared to paid. Good for news aggregation with basic sentiment.
- **Quality Rating:** 3.5/5

### 6.5 LunarCrush
- **URL:** https://lunarcrush.com/
- **API:** https://lunarcrush.com/about/api
- **Free Tier (Discover Plan):**
  - Basic social metrics
  - Limited data access
  - Galaxy Score (social sentiment metric)
- **Paid Plans:** Individual $24/mo, Builder $240/mo
- **Gotchas:** Free tier is severely limited. API access mostly requires paid plan.
- **Quality Rating:** 2/5 (free tier)

### 6.6 Google Trends (via pytrends)
- **URL:** https://github.com/GeneralMills/pytrends
- **Official API (Alpha, 2025):** https://developers.google.com/search/blog/2025/07/trends-api
- **Free Tier:**
  - pytrends: Completely free (unofficial scraper library)
  - Official Trends API: Alpha, limited endpoints and quotas
- **Data Available:**
  - Search interest over time for any keyword (e.g., "bitcoin", "ethereum", "crypto")
  - Related queries, regional interest
  - Real-time and historical trending
- **Gotchas:** pytrends is unofficial and may break if Google changes their service. Rate limiting issues (Google may block excessive requests). Data is relative (not absolute volumes). Official API is in alpha with limited access. The pytrends library has maintenance concerns.
- **Quality Rating:** 3/5

### 6.7 StockTwits
- **URL:** https://stocktwits.com/
- **Free Tier:** StockTwits had a free API but its current status and availability for crypto is uncertain. Check their developer page directly.
- **Quality Rating:** 2/5 (uncertain availability)

### 6.8 Telegram Monitoring (via Bot API)
- **URL:** https://core.telegram.org/bots/api
- **Free Tier:**
  - Completely free to create and run bots
  - 30 messages/second sending limit
  - Can monitor public channels/groups for sentiment
- **Gotchas:** You can build bots to monitor crypto Telegram channels for free. Rate limit: 30 msg/sec global, 1 msg/sec per chat, 20 msg/min per group. Building a proper sentiment pipeline from Telegram requires significant development effort.
- **Quality Rating:** 3.5/5 (for building custom monitoring)

---

## 7. FREE TECHNICAL ANALYSIS LIBRARIES <a name="7-free-technical-analysis-libraries"></a>

All of the following are 100% free and open-source.

### 7.1 TA-Lib (Technical Analysis Library)
- **URL:** https://ta-lib.org/ | Python wrapper: https://github.com/TA-Lib/ta-lib-python
- **License:** BSD (free for commercial use)
- **Indicators:** 200+ technical analysis functions
- **Categories:** Overlap Studies, Momentum, Volume, Volatility, Price Transform, Cycle, Pattern Recognition (61 candlestick patterns)
- **Gotchas:** C library requires separate installation. Can be tricky to install on Windows. Python wrapper (ta-lib) needs the C library pre-installed.
- **Quality Rating:** 5/5 -- Industry standard.

### 7.2 pandas-ta
- **URL:** https://github.com/twopirllc/pandas-ta | https://www.pandas-ta.dev/
- **License:** MIT (free for commercial use)
- **Indicators:** 150+ indicators and 60+ candlestick patterns (with TA-Lib installed)
- **Features:**
  - Native Pandas extension (df.ta.sma(), df.ta.macd(), etc.)
  - Numba/NumPy acceleration
  - Built-in multiprocessing via DataFrame strategy method
  - Tightly correlated with TA-Lib outputs
- **Gotchas:** Actively maintained fork: pandas-ta-classic with 200+ indicators. No C dependency issues (pure Python + NumPy).
- **Quality Rating:** 5/5 -- Best pure-Python TA library.

### 7.3 ta (Technical Analysis Library in Python)
- **URL:** https://technical-analysis-library-in-python.readthedocs.io/
- **License:** MIT
- **Indicators:** Comprehensive set including Bollinger Bands, MACD, RSI, Stochastic, Williams %R, CCI, ADI, OBV, ATR, and many more
- **Features:** Simple integration with pandas DataFrames
- **Quality Rating:** 4/5

### 7.4 Tulip Indicators
- **URL:** https://tulipindicators.org/
- **License:** LGPL v3 (free, including commercial use)
- **Indicators:** 100+ indicators in C library with Python bindings
- **Features:** Extremely fast C implementation
- **Quality Rating:** 3.5/5

### 7.5 Other Free TA Tools
- **finta:** pandas-based TA (MIT license)
- **Tulipy:** Python bindings for Tulip Indicators
- **bta-lib:** Backtrader's TA library (similar to TA-Lib API)

---

## 8. FREE DERIVATIVES DATA <a name="8-free-derivatives-data"></a>

### 8.1 Coinglass
- **URL:** https://www.coinglass.com/
- **API Pricing:** https://www.coinglass.com/pricing
- **Free Website Data:**
  - Funding rates (current + historical) across all major exchanges
  - Open interest (aggregated and per-exchange)
  - Liquidation data and heatmaps
  - Long/short ratios
  - Top trader positions
  - BTC/ETH options data
- **API Free Tier:** Coinglass appears to have a limited free API tier; however, their API plans are primarily paid. The WEBSITE provides extensive free visual data.
- **Gotchas:** Free website data is excellent for manual analysis. API access for automated systems likely requires paid plan. Web scraping their site is against ToS.
- **Quality Rating:** 4/5 (website); 2/5 (free API -- limited)

### 8.2 Exchange APIs (Free Derivatives Data)
These exchanges provide FREE API access to derivatives data:
- **Binance Futures:** Funding rates, OI, long/short ratio, taker buy/sell volume, liquidations -- all free via REST and WebSocket
- **Bybit:** Funding rates, OI, liquidations -- free API
- **OKX:** Funding rates, OI, long/short -- free API
- **Deribit:** Options data (greeks, IV, order book, trades) -- free API at https://docs.deribit.com/
- **Bitget:** Funding, OI -- free API
- **Gate.io:** Derivatives data -- free API

**Recommendation:** For derivatives data, use exchange APIs directly. They are the SOURCE of this data, and it's all free.

### 8.3 Deribit (Options Data)
- **URL:** https://docs.deribit.com/
- **Free Data:**
  - Full options chain (BTC, ETH)
  - Greeks (delta, gamma, theta, vega)
  - Implied volatility
  - Order book for options
  - Trade history
  - WebSocket streaming
- **Quality Rating:** 5/5 for crypto options data -- THE source.

### 8.4 Laevitas
- **URL:** https://www.laevitas.ch/ | https://docs.laevitas.ch/
- **Free Tier:**
  - Basic features accessible via free plan
  - Some dashboard data viewable without subscription
- **Paid Plans:** Premium $50/month
- **Data:** Options flow, funding rates, OI, Greeks, IV surfaces, historical data
- **Quality Rating:** 3/5 (free tier is limited)

### 8.5 The Block Data Dashboard
- **URL:** https://www.theblock.co/data/crypto-markets/spot
- **Free Data:**
  - Various crypto market charts and dashboards
  - Some derivatives data visualizations
  - Research articles
- **Gotchas:** Premium content requires subscription. Free charts are useful for reference but not API-accessible.
- **Quality Rating:** 3/5

### 8.6 Datamish
- **URL:** https://datamish.com/
- **Free Data:**
  - Bitfinex long/short positions for BTC
  - Bitmex liquidations
  - Health scores for longs and shorts
- **Completely Free:** Yes
- **Quality Rating:** 3/5 (limited to Bitfinex/Bitmex data)

### 8.7 Binance Futures Trading Data Page
- **URL:** https://www.binance.com/en/futures/funding-history/perpetual/trading-data
- **Free Data:**
  - Open interest, top trader long/short ratio
  - Long/short ratio, taker buy/sell volume
  - All accessible via API as well
- **Quality Rating:** 5/5 -- Free and directly from the largest exchange.

---

## 9. FREE NEWS/RSS FEEDS <a name="9-free-news-rss-feeds"></a>

### 9.1 Major Crypto News RSS Feeds (All Free)

| Source | RSS URL | Notes |
|--------|---------|-------|
| CoinTelegraph | https://cointelegraph.com/rss | Multiple feeds by topic |
| CoinDesk | https://www.coindesk.com/arc/outboundfeeds/rss/ | Full articles |
| Decrypt | https://decrypt.co/feed | Crypto and Web3 |
| The Block | https://www.theblock.co/rss | May be limited |
| CryptoPotato | https://cryptopotato.com/feed/ | News + analysis |
| Crypto Briefing | https://cryptobriefing.com/feed/ | Daily briefings |
| Bitcoin Magazine | https://bitcoinmagazine.com/.rss/full/ | Bitcoin-focused |
| NewsBTC | https://www.newsbtc.com/feed/ | Price analysis |

### 9.2 CryptoPanic (News Aggregator)
- **URL:** https://cryptopanic.com/
- **API:** https://cryptopanic.com/developers/api/
- **Free Tier:** Free API token available. Aggregates news from dozens of sources with sentiment tags.
- **Quality Rating:** 4/5

### 9.3 Building a Free News Pipeline
- Use Python `feedparser` library (free) to parse RSS feeds
- Combine multiple RSS sources into a single news stream
- Use NLP libraries (NLTK, TextBlob, VADER -- all free) for sentiment scoring
- Store in SQLite/PostgreSQL (free)
- **Total Cost:** $0

---

## 10. FREE BACKTESTING & ML TOOLS <a name="10-free-backtesting-ml-tools"></a>

### 10.1 Freqtrade
- **URL:** https://www.freqtrade.io/ | https://github.com/freqtrade/freqtrade
- **License:** GPL v3 (free, open-source)
- **Features:**
  - Complete crypto trading bot framework
  - Backtesting engine with detailed reporting
  - Strategy optimization via Hyperopt (machine learning)
  - Paper trading and live trading
  - Supports Binance, Bybit, OKX, Kraken, and more
  - Telegram integration for notifications
  - FreqUI web interface
- **Quality Rating:** 5/5 -- Best free crypto-specific backtesting/trading framework.

### 10.2 Backtrader
- **URL:** https://www.backtrader.com/ | https://github.com/mementum/backtrader
- **License:** GPL v3 (free)
- **Features:**
  - Event-driven backtesting engine
  - Highly extensible architecture
  - Custom indicators and strategies
  - Crypto exchange connectors available (via CCXT integration)
  - Plotting and analysis tools
- **Gotchas:** No longer actively maintained (last major update ~2020). Community forks exist.
- **Quality Rating:** 3.5/5

### 10.3 VectorBT
- **URL:** https://vectorbt.dev/ | https://github.com/polakowo/vectorbt
- **License:** Apache 2.0 with Commons Clause (free for non-SaaS use)
- **Features:**
  - Vectorized backtesting (extremely fast)
  - Test thousands of strategies in seconds
  - Built on pandas, NumPy, Numba
  - Portfolio optimization
  - Detailed analytics and plotting
- **Gotchas:** Commons Clause restricts selling VectorBT as a service. Learning curve is steeper than Freqtrade. VectorBT PRO is paid.
- **Quality Rating:** 4.5/5 for research and backtesting speed.

### 10.4 QuantConnect / Lean Engine
- **URL:** https://www.quantconnect.com/ | https://github.com/QuantConnect/Lean
- **Free Tier:**
  - Lean Engine: fully open-source (Apache 2.0)
  - Cloud backtesting: 8 hours/month free
  - Access to terabytes of free financial data (including crypto)
  - Paper trading: free
- **Live Trading Cost:** ~$28/month minimum (membership + node)
- **Data:** Free crypto data from major exchanges included
- **Gotchas:** Supports Python and C#. Cloud resources limited on free tier. Self-hosting Lean is free but requires your own data.
- **Quality Rating:** 4/5

### 10.5 TradingView Pine Script
- **URL:** https://www.tradingview.com/pine-script-docs/
- **Free Plan:**
  - Pine Script editor and execution: FREE
  - Backtesting on strategies: FREE
  - Access to public script library: FREE
  - Screener access: FREE
  - Limited to 1 chart layout, 3 indicators per chart
- **Gotchas:** Cannot export data easily. Strategies run on TradingView servers. Not suitable for automated execution without workarounds (webhooks). Free plan limits charts and alerts.
- **Quality Rating:** 3.5/5 (limited for quant systems, great for visual strategy testing)

### 10.6 Free Compute for ML

| Platform | Free Tier | GPU | Session Limit | Notes |
|----------|-----------|-----|---------------|-------|
| Google Colab | Free | T4 GPU (variable availability) | 12 hrs max | Compute units system; availability fluctuates |
| Kaggle Notebooks | Free | P100/T4, 30 GPU-hrs/week | 9 hrs/session | More reliable GPU allocation |
| Lightning.ai | Free | 22 GPU hours/month | Various | Good for PyTorch workloads |
| Gradient (Paperspace) | Free | Some free GPU access | 6 hrs | Limited availability |

### 10.7 Free ML Libraries (All Open-Source)
- **scikit-learn:** Classification, regression, clustering
- **XGBoost / LightGBM / CatBoost:** Gradient boosting (excellent for tabular financial data)
- **PyTorch / TensorFlow:** Deep learning (LSTM, Transformer models)
- **statsmodels:** Time series analysis (ARIMA, GARCH)
- **Prophet (by Meta):** Time series forecasting
- **Ray Tune:** Hyperparameter tuning (free, open-source)

---

## 11. FREE INFRASTRUCTURE <a name="11-free-infrastructure"></a>

### 11.1 Free Databases

| Database | Type | Free Option | Notes |
|----------|------|-------------|-------|
| **SQLite** | Relational | Built into Python | Perfect for small-medium datasets. No server needed. |
| **PostgreSQL** | Relational | Self-hosted (free) | Best for production. TimescaleDB extension for time-series. |
| **DuckDB** | Analytical | Open-source | Excellent for OLAP queries on OHLCV data. In-process. |
| **QuestDB** | Time-series | Open-source, free cloud tier | Purpose-built for time-series financial data. |
| **InfluxDB** | Time-series | Open-source | Good for real-time metrics and OHLCV storage. |

### 11.2 Free Redis Alternatives

| Service | Free Tier | Notes |
|---------|-----------|-------|
| **Valkey** | Open-source (BSD 3) | Redis fork by Linux Foundation. Self-host for free. |
| **Dragonfly** | Open-source | Redis-compatible, better performance. Self-host free. |
| **Upstash** | Free tier (serverless) | Limited free tier for prototyping. Managed cloud. |
| **Render** | Free Redis tier | Free managed Redis hosting. |

### 11.3 Free Cloud VPS/Compute

| Provider | Always Free? | Specs | Notes |
|----------|-------------|-------|-------|
| **Oracle Cloud** | YES, forever | 4 ARM cores, 24GB RAM (Ampere A1) + 2 AMD VMs (1/8 OCPU, 1GB each) + 10TB/mo outbound | **BEST free cloud tier available.** Can run trading bots 24/7 for free. |
| **AWS** | 12 months free, then Always Free tier | t2.micro (750hrs/mo for 12 months), Lambda (1M requests/mo forever), DynamoDB (25GB forever) | Good for Lambda-based cron jobs. |
| **Google Cloud** | 90 days + Always Free | e2-micro (1 instance), Cloud Functions, BigQuery (1TB/mo queries) | BigQuery free tier is excellent for data analysis. |
| **Azure** | 12 months + Always Free | B1s VM (750hrs/mo for 12 months), Functions, Cosmos DB | Azure Functions for event-driven processing. |

**Recommendation:** Oracle Cloud's always-free ARM instance (4 cores, 24GB RAM) is extraordinary for running a trading bot 24/7 at zero cost. This should be your primary infrastructure.

### 11.4 Free Monitoring

| Service | Free Tier | Notes |
|---------|-----------|-------|
| **Grafana Cloud** | 10K metrics, 50GB logs, 50K traces, 3 users, 14-day retention | Excellent for monitoring trading system health |
| **Uptime Robot** | 50 monitors, 5-min intervals | Monitor bot uptime |
| **Healthchecks.io** | 20 checks | Cron job monitoring |

### 11.5 Free Notification Services

| Service | Free Tier | Notes |
|---------|-----------|-------|
| **Telegram Bot API** | Completely free. 30 msg/sec limit. | BEST option for trading alerts. Free forever. |
| **Discord Webhooks** | Completely free | Alternative to Telegram |
| **Pushover** | 10,000 messages/month (one-time $5 app purchase) | Near-free mobile notifications |
| **Email (SMTP)** | Gmail: 500/day; SendGrid: 100/day free | For daily reports |

---

## 12. FREE TRADINGVIEW & CHARTING <a name="12-free-tradingview-charting"></a>

### 12.1 TradingView Lightweight Charts
- **URL:** https://www.tradingview.com/lightweight-charts/ | https://github.com/nicknacknow/lightweight-charts
- **License:** Apache 2.0 (fully free, including commercial)
- **Size:** ~45KB
- **Features:**
  - Candlestick, line, area, bar, histogram, baseline charts
  - Real-time updates
  - Custom themes and styling
  - Markers, price lines, series
- **Quality Rating:** 5/5 -- Best free financial charting library.

### 12.2 TradingView Advanced Charts
- **URL:** https://www.tradingview.com/advanced-charts/
- **Free:** Available for non-commercial personal projects. Commercial use requires enterprise license.
- **Features:** Full TradingView charting experience embeddable in web apps
- **Quality Rating:** 5/5 (but licensing restrictions apply)

### 12.3 Other Free Charting Options

| Library | URL | Notes |
|---------|-----|-------|
| **Plotly** | https://plotly.com/python/ | Excellent interactive charts, open-source |
| **mplfinance** | https://github.com/matplotlib/mplfinance | Matplotlib-based candlestick charts |
| **Bokeh** | https://bokeh.org/ | Interactive web plots |
| **Apache ECharts** | https://echarts.apache.org/ | Feature-rich, free charting |
| **Chart.js** | https://www.chartjs.org/ | Lightweight web charting |

---

## SUMMARY: RECOMMENDED FREE STACK

Based on this research, here is the optimal free stack for a cryptocurrency quantitative trading system:

### Data Collection Layer
| Need | Recommended Free Source |
|------|----------------------|
| **Real-time prices** | Binance WebSocket (free) via direct API or CCXT |
| **Historical OHLCV** | Binance data.binance.vision (bulk download) + API for updates |
| **Order book** | Binance/Bybit WebSocket |
| **Funding rates** | Binance Futures API (free) |
| **Open interest** | Binance Futures API + Bybit API |
| **On-chain data** | DeFiLlama (free API) + Dune Analytics (2,500 credits/mo) |
| **Sentiment** | Alternative.me Fear & Greed (free API) + Reddit via PRAW |
| **News** | RSS feeds (CoinTelegraph, CoinDesk, Decrypt) via feedparser |
| **Options data** | Deribit API (free) |
| **Market overview** | CoinGecko Demo API (30 req/min, 10K/month) |

### Analysis & Backtesting Layer
| Need | Recommended Free Tool |
|------|---------------------|
| **Technical indicators** | pandas-ta (free) or TA-Lib (free) |
| **Backtesting** | Freqtrade (free) or VectorBT (free) |
| **ML/AI** | scikit-learn + XGBoost (free) on Kaggle/Colab |
| **Charting** | TradingView Lightweight Charts or Plotly |

### Infrastructure Layer
| Need | Recommended Free Option |
|------|------------------------|
| **VPS (24/7 bot)** | Oracle Cloud Always Free (4 ARM cores, 24GB RAM) |
| **Database** | PostgreSQL (self-hosted on Oracle) or SQLite |
| **Cache** | Valkey (self-hosted, free) |
| **Monitoring** | Grafana Cloud free tier |
| **Alerts** | Telegram Bot API (free) |
| **Notebooks** | Kaggle (30 GPU-hrs/week) or Google Colab |

### Total Monthly Cost: $0

---

## KEY GOTCHAS AND WARNINGS

1. **Rate Limits Are Real:** Always implement proper rate limiting, backoff, and caching. Getting IP-banned from Binance will cripple your data pipeline.

2. **Twitter/X Is Dead for Free Sentiment:** Do not plan around Twitter data unless you budget $200+/month. Use Reddit, CryptoPanic, and Google Trends instead.

3. **Binance data.binance.vision Is Your Best Friend:** For historical backtesting, download bulk data files. Do NOT try to collect years of 1m candles via API -- it will take forever and risk rate limit bans.

4. **Exchange APIs Are the Primary Source:** Third-party data APIs (CoinGecko, CoinMarketCap, etc.) are great for overview data but add latency and introduce rate limits. For trading, go directly to exchange APIs.

5. **Oracle Cloud Free Tier Is Extraordinary:** 4 ARM cores + 24GB RAM for free, forever. This is where your bot should run.

6. **DeFiLlama Is the Best Free DeFi Data Source:** Completely free, open-source, comprehensive TVL and protocol data. Essential for DeFi-related strategies.

7. **CCXT Is Essential:** Even if you use exchange APIs directly for production, CCXT is invaluable for research and prototyping across exchanges.

8. **Data Quality Varies:** Free data from aggregators may have gaps, delays, or inconsistencies. Always validate against exchange source data.

---

*Report compiled February 2026. Prices, rate limits, and free tier offerings are subject to change. Always verify current terms on official websites before building production systems.*
