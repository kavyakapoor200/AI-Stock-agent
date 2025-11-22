
# app.py
import os
import requests
import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt

# ---------------------------
#  MISTRAL API (no key in code)
# ---------------------------
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")  # set this in your terminal or .env

def mistral_llm(prompt):
    """Call Mistral Chat Completions API and return assistant content or error message."""
    url = "https://api.mistral.ai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "mistral-medium-latest",
        "messages": [{"role": "user", "content": prompt}]
    }

    response = requests.post(url, json=payload, headers=headers)
    try:
        data = response.json()
    except Exception as e:
        return f"API/Network error: {e}"

    # debug - remove/comment in production if not needed
    # st.write("RAW Mistral response (debug):", data)

    if "choices" not in data:
        return f"API Error: {data}"

    return data["choices"][0]["message"]["content"]


def query_llm(prompt):
    return mistral_llm(prompt)


# ---------------------------
#   STOCK FUNCTIONS
# ---------------------------
def fetch_stock_price(ticker: str):
    """Fetch today's close price for the ticker."""
    try:
        stock = yf.Ticker(ticker)
        price_data = stock.history(period="1d")["Close"]
        if price_data.empty:
            return f" No data found for {ticker} (may be delisted or invalid)." 
        return f" **Current price of {ticker}:** ${price_data.iloc[-1]:.2f}" 
    except Exception as e:
        return f" Error fetching stock data for {ticker}: {e}" 


def plot_stock(ticker):
    """Fetch 1 month history and return a saved plot image path."""
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
    """Dynamically detect valid stock tickers using yfinance."""
    words = query.upper().split()
    tickers = []

    for w in words:
        if not w.isalpha() or not (1 <= len(w) <= 5):
            continue

        try:
            stock = yf.Ticker(w)
            hist = stock.history(period="1d")

            if hist.empty:
                continue

            tickers.append(w)

        except Exception:
            continue

    return tickers


def get_company_info(ticker):
    """Fetch company details from yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

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
            f" **Company:** {name}\n" 
            f" **Sector:** {sector}\n" 
            f" **Industry:** {industry}\n" 
            f" **Market Cap:** {market_cap}\n" 
            f" **Website:** {website}\n" 
        )

    except Exception:
        return " No company info available." 


def explain_stock_movement(ticker, history):
    """Use Mistral LLM to explain trend."""
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

    Explain the trend in simple words (no financial advice).
    """

    return mistral_llm(prompt)


# ---------------------------
#   AGENT LOGIC
# ---------------------------
def agent_response_text(query: str):
    """
    Auto-detect tickers.
    If tickers exist -> fetch stock price, company info, chart, and AI analysis.
    Otherwise -> answer from LLM.
    """
    results = []

    tickers = extract_tickers(query)

    if tickers:
        results.append(f"🔍 Detected tickers: {', '.join(tickers)}")

        for t in tickers:
            # 1. Stock Price
            results.append(fetch_stock_price(t))

            # 2. Company Info
            info = get_company_info(t)
            results.append(info)

            # 3. Chart + history
            stock = yf.Ticker(t)
            history = stock.history(period="1mo")
            plot_path = plot_stock(t)
            if plot_path:
                results.append(plot_path)

            # 4. AI Trend Explanation
            explanation = explain_stock_movement(t, history)
            results.append(f" **AI Insight for {t}:**\n{explanation}") 

        return results

    else:
        return [query_llm(query)]


# ---------------------------
#    STREAMLIT UI
# ---------------------------
st.set_page_config(page_title="AI Stock Agent", layout="wide")
st.title("📊 AI Stock Agent (Mistral API + Streamlit)")
st.write("Ask anything or request stock prices. Example: `stock price of TSLA and AAPL`")

# Sidebar: show status and instructions
with st.sidebar:
    st.header("Settings / Info")
    st.write("- Make sure `MISTRAL_API_KEY` environment variable is set.")
    st.write("- Built with Mistral 7B (API), yfinance, Streamlit.")
    if MISTRAL_API_KEY is None:
        st.error("MISTRAL_API_KEY is not set! Set it before running the app.")
    st.markdown("---")
    st.markdown("**How to ask**")
    st.write("• Stock price: `stock price of TSLA`")
    st.write("• General question: `Explain machine learning`")

# Main input
user_query = st.text_input("Enter your query here:", value="")

if st.button("Run Agent"):
    if not user_query or user_query.strip() == "":
        st.warning("Please type a query.")
    else:
        with st.spinner("Agent is thinking..."):
            outputs = agent_response_text(user_query)

        # show outputs: strings or png filepaths
        for out in outputs:
            if isinstance(out, str) and out.lower().endswith(".png"):
                try:
                    st.image(out, use_column_width=True)
                except Exception:
                    st.write(f"(Could not display image file: {out})")
            else:
                st.write(out)

# Optional: keep a simple history in the session
if "history" not in st.session_state:
    st.session_state.history = []

if user_query:
    if st.button("Save to history"):
        st.session_state.history.append(user_query)
        st.success("Saved to history")

if st.session_state.history:
    st.markdown("### 🔁 Query History")
    for i, q in enumerate(reversed(st.session_state.history[-10:]), 1):
        st.write(f"{i}. {q}")
