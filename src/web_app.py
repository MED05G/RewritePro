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
    if article_type == "travel":
        return f"""
        Rewrite the following travel article in 800 words, avoiding plagiarism. Follow these strict guidelines:

        1. Start with an interactive greeting (e.g., “Friends,” “Readers,” “Lykkers”).
        2. Use <h3> for each section heading (max 3 words); begin the intro and end with a conclusion.
        3. Each paragraph must be under 4 lines.
        4. Highlight key terms (locations, concepts, etc.) with <b> and </b>.
        5. Ensure specific, vivid detail: include costs, transportation, time info, etc.
        6. Avoid first-person language and vague writing.
        7. The content must reflect E-E-A-T.
        8. Avoid inappropriate content: religion, war, politics, pork, beef, alcohol, nudity, etc.
        9. Grammar must be native-level.
        10. End with:
            - A creative title (≤28 chars)
            - A vivid summary (≤20 words)

        Article:

        {text}
        """

    elif article_type == "food":
        return f"""
        Rewrite the following food/recipe article in 800 words, avoiding plagiarism. Structure and format as follows:

        1. Warm greeting (e.g., “Lykkers, ready for a tasty treat?”).
        2. Use <h3> subheadings (e.g., <h3>Ingredients</h3>, <h3>Steps</h3>).
        3. Each paragraph under 4 lines.
        4. Highlight key terms with <b>.
        5. For recipes, include:
            - Exact ingredient list
            - Step-by-step numbered instructions
        6. Add value: flavor notes, tips, presentation, background.
        7. Use clear, natural tone. No generic advice or first-person.
        8. Avoid inappropriate topics.
        9. End with:
            - Catchy title (≤28 chars)
            - Summary (≤20 words)

        Article:

        {text}
        """
    else:
        raise ValueError("Invalid article_type; choose 'travel' or 'food'.")


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
# Streamlit UI (Clean)
# ------------------------

st.set_page_config(page_title="RewritePro", layout="centered")
st.title("📄 RewritePro")

article_type = st.radio("Choose article type:", ("travel", "food"))
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
                filename = f"{''.join(c if c.isalnum() else '_' for c in title)[:50]}_{i}.txt"
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
