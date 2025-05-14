import os
import time
import random
import logging
import streamlit as st
from openai import OpenAI
from newspaper import Article
from dotenv import load_dotenv
import io
import zipfile

# ----------------------------------
# 1) PAGE STYLING & GLOBAL SETTINGS
# ----------------------------------
st.set_page_config(page_title="🖌️ RewritePro", layout="wide")

# Custom CSS for styling
st.markdown(
    """
    <style>
        /* Center and style the main title */
        .main-title {
            text-align: center;
            font-size: 3rem;
            font-weight: bold;
            background: linear-gradient(90deg, #FF8A00, #E52E71);
            -webkit-background-clip: text;
            color: transparent;
        }
        /* Style the subtitle */
        .sub-title {
            text-align: center;
            font-size: 1.2rem;
            color: #555;
            margin-bottom: 2rem;
        }
        /* Style the radio buttons horizontally */
        .stRadio > div {
            flex-direction: row;
            gap: 1rem;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("<div class='main-title'>🖌️ RewritePro 🖌️</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Your AI‑powered Article Rewriter</div>", unsafe_allow_html=True)

# -------------------------------
# 2) ENVIRONMENT & OPENAI CLIENT
# -------------------------------
dotenv_path = os.getenv('DOTENV_PATH', None)
if dotenv_path:
    load_dotenv(dotenv_path)
else:
    load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    st.error("❌ OPENAI_API_KEY is missing. Please set it in your .env file.")
    st.stop()

client = OpenAI(base_url='https://xiaoai.plus/v1', api_key=OPENAI_API_KEY)

# -------------------------------
# 3) HELPER FUNCTIONS
# -------------------------------
def extract_text_from_url(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text or '', article.title or 'article'
    except Exception as e:
        logging.error(f"Failed to extract from {url}: {e}")
        return None, None

def get_prompt(text, article_type):
    core = f"""
Rewrite the following article in about 600–800 words (no less than 600), avoiding plagiarism. Follow the structure and instructions below carefully:

1. Start with an interactive intro (use “Lykkers”, “Friends”, or “Readers” when appropriate).
2. Be specific, vivid, and thematic—avoid vague writing.
3. Use clear subheadings. Each paragraph must:
   • Have a subtitle ≤3 words.
   • Be ≤4 lines.
   • Begin with <h3> and end with </h3>.
4. Bold all important terms with <b> and </b>.
5. Avoid first-person language.
6. No grammatical errors or AI‑style phrasing.
7. Follow E‑E‑A‑T principles.
8. Ensure correct English punctuation.
9. Prohibited topics: war, religion, alcohol, nudity, politics, pork, beef, LGBTQ+ references, bars/clubs, skin color.
10. Last paragraph is a reflective, actionable conclusion.

Article:
{text}
"""
    # Per‐type specialties
    if article_type == "food":
        extra = """
Additional for Food:
- Warm, sensory style: focus on taste, texture, aroma, presentation.
- Include specific ingredients, techniques, local context.
- Provide approximate ingredient costs, prep time, and tools.
"""
    elif article_type == "travel":
        extra = """
Additional for Travel:
- Vivid scene: places, activities, transport, local culture, exact locations.
- Include budget tips: routes, times, costs, packing list.
- Highlight hidden gems or local secrets.
"""
    elif article_type == "medical":
        extra = """
Additional for Medical:
- Professional tone, expert‑backed content.
- Explain symptoms, diagnostic steps, treatments, when to seek care.
- Reference authoritative terms (e.g., <b>CDC guidelines</b>, <b>clinical trials</b>).
- Comply with YMYL: factual, no sensationalism.
"""
    elif article_type == "finance":
        extra = """
Additional for Finance:
- Clear actionable advice: managing debt, saving, investing basics.
- Include figures: fees, rates, common pitfalls.
- Tone may be professional or relatable.
- Live examples: <b>credit score</b>, <b>loan interest</b>, <b>emergency fund</b>.
"""
    elif article_type == "general":
        extra = """
Additional for General:
- Clear, relaxed tone with everyday examples.
- Offer fresh perspective on lifestyle/knowledge topics.
- Avoid clichés or overly broad statements.
"""
    else:
        raise ValueError("Invalid article_type")

    ending = """
Finally:
- Provide a global title ≤28 characters (creative, engaging).
- Provide a summary ≤20 words using rhetoric (suspense, exaggeration, question, reversal).
"""
    return core + extra + ending

def rewrite_article(text, article_type):
    prompt = get_prompt(text, article_type)
    backoff = 1.0
    for attempt in range(1, 4):
        try:
            res = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a professional editor creating high-quality, family-friendly content."},
                    {"role": "user",   "content": prompt}
                ],
                timeout=60
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"Attempt {attempt} failed: {e}")
            time.sleep(backoff + random.random()*0.5)
            backoff *= 2
    return None

# -------------------------------
# 4) STREAMLIT UI LAYOUT
# -------------------------------

# 4.1 Article type selector
choice = st.radio(
    "**Choose Article Type:**",
    ("🍲 Food", "🌍 Travel", "🏥 Medical", "💰 Finance", "📝 General"),
    index=0
)
article_type = choice.split()[1].lower()

# 4.2 URL input area
urls_input = st.text_area(
    "🖇️  Paste your article URLs (one per line):",
    height=200,
    placeholder="https://example.com/article1\nhttps://example.com/article2"
)

# 4.3 Action button
start = st.button("🚀 Rewrite & Zip")

if start:
    urls = [u.strip() for u in urls_input.splitlines() if u.strip()]
    if not urls:
        st.warning("⚠️ Please enter at least one URL.")
        st.stop()

    zip_buffer = io.BytesIO()
    success = 0
    progress = st.progress(0)
    total = len(urls)

    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zf:
        for idx, url in enumerate(urls, start=1):
            text, title = extract_text_from_url(url)
            if not text:
                continue
            rewritten = rewrite_article(text, article_type)
            if not rewritten:
                continue
            safe = "".join(c if c.isalnum() else "_" for c in title)[:50]
            filename = f"{safe}_{idx}.txt"
            content  = f"// {title} //\nSource: {url}\n\n{rewritten}"
            zf.writestr(filename, content)
            success += 1
            progress.progress(idx / total)

    zip_buffer.seek(0)
    if success:
        st.success(f"✅ {success} article(s) rewritten and ready!")
        st.download_button(
            "📦 Download ZIP of Rewritten Articles",
            data=zip_buffer,
            file_name="rewritten_articles.zip",
            mime="application/zip"
        )
    else:
        st.error("❌ No articles could be processed. Please check your URLs.")
