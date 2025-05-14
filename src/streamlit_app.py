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

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Load environment variables
dotenv_path = os.getenv('DOTENV_PATH', None)
if dotenv_path:
    load_dotenv(dotenv_path)
else:
    load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    st.error("❌ OPENAI_API_KEY is missing. Please set it in your .env file.")
    st.stop()

# Initialize OpenAI client
client = OpenAI(
    base_url='https://xiaoai.plus/v1',
    api_key=OPENAI_API_KEY
)


def extract_text_from_url(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        text = article.text or ''
        title = article.title or 'article'
        logging.info(f"Extracted {len(text)} characters from {url}")
        return text, title
    except Exception as e:
        logging.error(f"Failed to extract from {url}: {e}")
        return None, None


def get_prompt(text, article_type):
    core = f"""
Rewrite the following article in about 600–800 words (no less than 600), avoiding plagiarism. Follow the structure and instructions below carefully:

1. Start with an interactive intro (use “Lykkers”, “Friends”, or “Readers” when appropriate).
2. Be specific, vivid, and thematic—avoid vague writing.
3. Use clear subheadings. Each paragraph must:
   - Have a subtitle ≤3 words.
   - Be ≤4 lines.
   - Begin with <h3> and end with </h3>.
4. Bold all important terms with <b> and </b>.
5. Avoid first-person language.
6. No grammatical errors or AI‑style phrasing.
7. Follow E‑E‑A‑T principles.
8. Ensure correct English punctuation.
9. Prohibited topics: war, religion, alcohol, nudity, politics, pork, beef, LGBTQ+ references, bars/clubs, skin color.
10. Last paragraph is a reflective, actionable conclusion.
"""

    if article_type == "food":
        spec = """
Additional for **Food**:
- Warm, sensory style: focus on taste, texture, aroma, presentation.
- Include specific ingredients, techniques, local context.
- Provide approximate ingredient costs, prep time, tools.
"""
    elif article_type == "travel":
        spec = """
Additional for **Travel**:
- Vivid scene: places, activities, transport, local culture, exact locations.
- Include budget tips: routes, times, costs, packing list.
- Highlight hidden gems or local secrets.
"""
    elif article_type == "medical":
        spec = """
Additional for **Medical**:
- Professional tone, expert‑backed content.
- Explain symptoms, diagnosis steps, treatments, when to seek care.
- Reference authoritative terms (e.g., <b>CDC guidelines</b>, <b>clinical trials</b>).
- Comply with YMYL: factual, no sensationalism.
"""
    elif article_type == "finance":
        spec = """
Additional for **Finance**:
- Clear actionable advice: managing debt, saving, investing basics.
- Include figures: fees, rates, common pitfalls.
- Tone may be professional or relatable.
- Live examples: <b>credit score</b>, <b>loan interest</b>, <b>emergency fund</b>.
"""
    elif article_type == "general":
        spec = """
Additional for **General**:
- Clear, relaxed tone with everyday examples.
- Offer fresh perspective on lifestyle/knowledge topics.
- Avoid clichés or overly broad statements.
"""
    else:
        raise ValueError("Invalid article_type; choose 'food', 'travel', 'medical', 'finance', or 'general'.")

    ending = """
Finally:
- Provide a global title ≤28 characters (creative, engaging).
- Provide a summary ≤20 words using rhetoric (suspense, exaggeration, question, reversal).
Article:
{text}
"""
    return (core + spec + ending).format(text=text)


def rewrite_article(text, article_type):
    prompt = get_prompt(text, article_type)
    backoff = 1.0
    for attempt in range(1, 4):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a professional editor creating high-quality, family-friendly content."},
                    {"role": "user", "content": prompt}
                ],
                timeout=60
            )
            content = response.choices[0].message.content.strip()
            word_count = len(content.split())
            if 600 <= word_count <= 800:
                return content
            logging.warning(f"Word count {word_count} out of range.")
            return content
        except Exception as e:
            logging.error(f"Attempt {attempt} error: {e}")
            time.sleep(backoff + random.random() * 0.5)
            backoff *= 2
    return None


# ------------------------
# Streamlit UI
# ------------------------

st.set_page_config(page_title="RewritePro", layout="centered")
st.title("📄 RewritePro")

article_type = st.radio(
    "Choose article type:",
    ("food", "travel", "medical", "finance", "general")
)

url_input = st.text_area("Paste article URLs (one per line):", height=200)
start = st.button("🛠 Rewrite and Prepare ZIP")

if start:
    urls = [line.strip() for line in url_input.split("\n") if line.strip()]
    if not urls:
        st.warning("⚠️ Please paste at least one URL.")
        st.stop()

    zip_buffer = io.BytesIO()
    success_count = 0

    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
        with st.spinner("Processing articles..."):
            for i, url in enumerate(urls, 1):
                text, title = extract_text_from_url(url)
                if not text:
                    continue
                rewritten = rewrite_article(text, article_type)
                if not rewritten:
                    continue
                safe_title = ''.join(c if c.isalnum() else '_' for c in title)[:50]
                filename = f"{safe_title}_{i}.txt"
                content = f"// {title} //\nSource: {url}\n\n{rewritten}"
                zip_file.writestr(filename, content)
                success_count += 1

    zip_buffer.seek(0)

    if success_count:
        st.success(f"✅ {success_count} article(s) rewritten and zipped.")
        st.download_button(
            label="📦 Download ZIP of Rewritten Articles",
            data=zip_buffer,
            file_name="rewritten_articles.zip",
            mime="application/zip"
        )
    else:
        st.error("❌ No articles could be processed.")
