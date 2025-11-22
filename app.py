# app.py
import os
import requests
import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt

# ---------------------------
#  MISTRAL API
# ---------------------------
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

def mistral_llm(prompt):
    """Call Mistral Chat Completions API."""
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-medium-latest",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
    except Exception as e:
        return f"❌ API/Network error: {e}"

    if "choices" not in data:
        return f"❌ API Error: {data}"

    return data["choices"][0]["message"]["content"]


def query_llm(prompt):
    return mistral_llm(prompt)


# ---------------------------
#   STOCK FUNCTIONS
# ---------------------------
def fetch_stock_price(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        price_data = stock.history(period="1d")["Close"]
        if price_data.empty:
            return f"❌ No data found for **{ticker}** (may be invalid)."
        return f"💰 **Current price of {ticker}:** `${price_data.iloc[-1]:.2f}`"
    except Exception as e:
        return f"❌ Error fetching stock data for {ticker}: {e}"


def plot_stock(ticker):
    """Returns plot file path."""
    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period="1mo")

        if history.empty:
            return None

        plt.figure(figsize=(8, 4))
        plt.plot(history.index, history["Close"], marker="o", linewidth=2)
        plt.title(f"{ticker} — 1 Month Trend")
        plt.xlabel("Date")
        plt.ylabel("Close Price")
        plt.grid(True)

        filepath = f"{ticker}_plot.png"
        plt.tight_layout()
        plt.savefig(filepath)
        plt.close()
        return filepath
    except Exception:
        return None


def extract_tickers(query):
    """Dynamic ticker detection."""
    words = query.upper().split()
    tickers = []

    for w in words:
        if not w.isalpha() or not (1 <= len(w) <= 5):
            continue

        try:
            stock = yf.Ticker(w)
            hist = stock.history(period="1d")
            if not hist.empty:
                tickers.append(w)
        except:
            pass

    return tickers


def get_company_info(ticker):
    """Fetch company details."""
    try:
        info = yf.Ticker(ticker).info

        name = info.get("longName", "N/A")
        sector = info.get("sector", "N/A")
        industry = info.get("industry", "N/A")
        market_cap = info.get("marketCap", None)
        website = info.get("website", "N/A")

        if market_cap:
            market_cap = f"${market_cap/1e9:.2f}B"
        else:
            market_cap = "N/A"

        return (
            f"🏢 **Company:** {name}\n"
            f"🏭 **Sector:** {sector}\n"
            f"🔧 **Industry:** {industry}\n"
            f"💰 **Market Cap:** {market_cap}\n"
            f"🔗 **Website:** {website}\n"
        )

    except:
        return "ℹ️ Company info unavailable."


def explain_stock_movement(ticker, history):
    """Generate AI-based stock trend explanation."""
    if history is None or history.empty:
        return "No trend data available."

    start_price = history["Close"].iloc[0]
    end_price = history["Close"].iloc[-1]
    percent_change = ((end_price - start_price) / start_price) * 100

    prompt = f"""
    Analyze the last 1-month price movement of {ticker}.

    Start Price: {start_price:.2f}
    End Price: {end_price:.2f}
    Percentage Change: {percent_change:.2f}%

    Give a simple explanation (no financial advice).
    """

    return mistral_llm(prompt)


# ---------------------------
#   AGENT LOGIC
# ---------------------------

FINANCE_KEYWORDS = [
    "stock", "stocks", "price", "market", "finance", "financial", "invest",
    "investment", "investing", "trend", "chart", "company", "earning",
    "earnings", "revenue", "profit", "loss", "valuation", "ipo",
    "dividend", "share", "shares", "portfolio", "asset", "fund", 
    "etf", "nasdaq", "nyse", "sensex", "nifty", "broker", "trading",
    "pe", "p/e", "ratio", "volume", "close", "opening", "intraday"
]

def agent_response_text(query: str):
    """
    Smart finance agent:
    Ticker → full stock analysis
    Finance theory → LLM explanation
    Non-finance → reject
    """
    query_lower = query.lower()
    results = []

    # --- 1) DETECT TICKERS ---
    tickers = extract_tickers(query)

    # --- 2) STOCK MODE: VALID TICKERS FOUND ---
    if tickers:
        results.append(f" **Detected tickers:** {', '.join(tickers)}")

        for t in tickers:
            # PRICE
            results.append(fetch_stock_price(t))

            # COMPANY INFO
            results.append(get_company_info(t))

            # CHART
            stock = yf.Ticker(t)
            history = stock.history(period="1mo")
            plot_path = plot_stock(t)
            if plot_path:
                results.append({"type": "image", "path": plot_path})

            # AI TREND INSIGHT
            explanation = explain_stock_movement(t, history)
            results.append(f" **AI Insight for {t}:**\n{explanation}")

        return results

    # --- 3) FINANCE QUERY WITHOUT TICKER ---
    if any(kw in query_lower for kw in FINANCE_KEYWORDS):
        # give LLM explanation
        return [query_llm(query)]

    # --- 4) NON-FINANCE QUERY ---
    return [" This agent only handles stock & finance-related queries."]
# ---------------------------
#    STREAMLIT UI
# ---------------------------
st.set_page_config(page_title="AI Stock Agent", layout="wide")
st.title(" AI Stock Agent (Mistral + Streamlit + Finance)")
st.write("Ask anything! Example: **TSLA**, **How is MSFT performing today?**, **Explain AI**")

# Sidebar
with st.sidebar:
    st.header(" Info")
    st.write("Built with:")
    st.write("- Mistral API")
    st.write("- yfinance")
    st.write("- Streamlit")
    st.write("- Python Agents")

    if not MISTRAL_API_KEY:
        st.error(" MISTRAL_API_KEY not set!")

# User Input
query = st.text_input("Enter your query:")

if st.button("Run Agent"):
    if not query.strip():
        st.warning("Please type a question.")
    else:
        with st.spinner("Thinking..."):
            results = agent_response_text(query)

        for item in results:
            if isinstance(item, dict) and item.get("type") == "image":
                st.image(item["path"], use_container_width=True)
            else:
                st.markdown(item)

# Query History
if "history" not in st.session_state:
    st.session_state.history = []

if query:
    if st.button("Save Query"):
        st.session_state.history.append(query)
        st.success("Saved!")

if st.session_state.history:
    st.subheader(" Recent History")
    for h in reversed(st.session_state.history[-10:]):
        st.write(f"- {h}")
