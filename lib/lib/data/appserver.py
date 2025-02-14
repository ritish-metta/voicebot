from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import re
import nltk
import requests
import os
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from textblob import TextBlob
from waitress import serve
import urllib.parse
import time
from functools import wraps
import logging
from datetime import datetime
from dotenv import load_dotenv
import os


# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chatbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Error handling decorator
def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}", exc_info=True)
            return jsonify({
                "error": "Internal server error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }), 500
    return decorated_function

# Download NLTK resources with error handling
def download_nltk_resources():
    resources = ['punkt', 'stopwords', 'averaged_perceptron_tagger']
    for resource in resources:
        try:
            if resource == 'punkt':
                nltk.data.find(f'tokenizers/{resource}')
            else:
                nltk.data.find(f'corpora/{resource}')
        except LookupError:
            try:
                nltk.download(resource)
                logger.info(f"Successfully downloaded NLTK resource: {resource}")
            except Exception as e:
                logger.error(f"Failed to download NLTK resource {resource}: {str(e)}")
                raise

try:
    download_nltk_resources()
except Exception as e:
    logger.error(f"Failed to initialize NLTK resources: {str(e)}")
    raise

# Default training data
DEFAULT_TRAINING_DATA = [
    {"query": "hello", "response": "Hi! How can I help you today?"},
    {"query": "how are you", "response": "I'm doing well, thank you for asking!"},
    {"query": "what is your name", "response": "I'm a chatbot assistant, nice to meet you!"},
    {"query": "goodbye", "response": "Goodbye! Have a great day!"},
    {"query": "thanks", "response": "You're welcome!"}
]

# Initialize caches with TTL
class TTLCache:
    def __init__(self, ttl_seconds=600):
        self.cache = {}
        self.ttl = ttl_seconds

    def get(self, key):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None

    def set(self, key, value):
        self.cache[key] = (value, time.time())

wikipedia_cache = TTLCache()
news_cache = TTLCache()

# Initialize training data
def initialize_training_data():
    data_dir = 'lib/data'
    file_path = os.path.join(data_dir, 'training_data.json')
    
    try:
        os.makedirs(data_dir, exist_ok=True)
        
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(DEFAULT_TRAINING_DATA, file, indent=4)
            logger.info("Created new training data file with default data")
            return DEFAULT_TRAINING_DATA

        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            logger.info("Successfully loaded existing training data")
            return data
    except Exception as e:
        logger.error(f"Error initializing training data: {str(e)}")
        return DEFAULT_TRAINING_DATA

training_data = initialize_training_data()

# Improved text preprocessing
def preprocess_text(text):
    try:
        # Basic cleaning
        text = text.strip()
        if not text:
            return ""

        # Spell correction
        corrected_text = str(TextBlob(text).correct())
        
        # Remove special characters but keep basic punctuation
        cleaned_text = re.sub(r'[^a-zA-Z0-9\s.,!?]', '', corrected_text.lower())
        
        # Tokenization
        words = word_tokenize(cleaned_text)
        
        # Remove stopwords
        stop_words = set(stopwords.words('english'))
        filtered_words = [word for word in words if word.lower() not in stop_words]
        
        return ' '.join(filtered_words)
    except Exception as e:
        logger.error(f"Error in text preprocessing: {str(e)}")
        return text

# Improved Wikipedia fetching
def fetch_from_wikipedia(query):
    try:
        # Check cache first
        cached_result = wikipedia_cache.get(query)
        if cached_result:
            return cached_result

        encoded_query = urllib.parse.quote(query)
        response = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_query}",
            timeout=10,
            headers={'User-Agent': 'ChatbotApp/1.0'}
        )
        response.raise_for_status()

        data = response.json()
        extract = data.get('extract') or data.get('description') or 'No information available.'
        
        # Cache the result
        wikipedia_cache.set(query, extract)
        return extract

    except requests.Timeout:
        logger.error("Wikipedia API request timed out")
        return "Request timed out. Please try again later."
    except requests.RequestException as e:
        logger.error(f"Wikipedia API error: {str(e)}")
        return "Sorry, I couldn't fetch Wikipedia data at the moment."
    except Exception as e:
        logger.error(f"Unexpected error fetching Wikipedia data: {str(e)}")
        return "An unexpected error occurred while fetching information."


        news_cache = {}
# Improved text preprocessing
logger = logging.getLogger(__name__)
        

# Improved news fetching
def fetch_news(query=None, country="us", category="business"):
    try:
        # Generate cache key
        cache_key = f"{query or category}-{country}"
        cached_result = news_cache.get(cache_key)
        if cached_result:
            return cached_result

        api_key = os.getenv('NEWS_API_KEY', '4cc3bf0cc5424522a615d94250eff225')
        base_url = "https://newsapi.org/v2"

        # Define multiple news sources based on category or query
        news_sources = {
            "business": [
                f"{base_url}/top-headlines?country={country}&category=business&apiKey={api_key}"
            ],
            "tech": [
                f"{base_url}/top-headlines?sources=techcrunch&apiKey={api_key}",
                f"{base_url}/everything?q=technology&apiKey={api_key}"
            ],
            "domains": [
                f"{base_url}/everything?domains=wsj.com&apiKey={api_key}"
            ],
            "apple": [
                f"{base_url}/everything?q=apple&from=2025-02-12&to=2025-02-12&sortBy=popularity&apiKey={api_key}"
            ],
            "tesla": [
                f"{base_url}/everything?q=tesla&from=2025-01-13&sortBy=publishedAt&apiKey={api_key}"
            ]
        }

        # Get URLs based on query or category
        urls = news_sources.get(query.lower(), news_sources.get(category.lower(), []))

        all_articles = []
        for url in urls:
            response = requests.get(url, timeout=15, headers={'User-Agent': 'ChatbotApp/1.0'})
            response.raise_for_status()
            articles = response.json().get('articles', [])
            all_articles.extend(articles)

        if not all_articles:
            return f"No news articles found for {query or category} in {country.upper()}."

        # Format results
        news_results = [f"📰 *Latest {query.capitalize() if query else category.capitalize()} News:*\n"]
        for article in all_articles[:5]:  # Limit to top 5 articles
            news_results.append(
                f"• *{article.get('title', 'No Title')}*\n"
                f"  Published: {article.get('publishedAt', '')[:10]}\n"
                f"  {article.get('description', 'No description available.')}\n"
                f"  [Read more]({article.get('url', '#')})\n"
            )

        result = '\n'.join(news_results)
        news_cache[cache_key] = result  # Cache result
        return result

    except requests.RequestException as e:
        logger.error(f"News API request failed: {str(e)}")
        return "Sorry, I couldn't fetch the news at the moment. Please try again later."
    except Exception as e:
        logger.error(f"Unexpected error in fetch_news: {str(e)}")
        return "An unexpected error occurred while fetching news."
    try:
        # Generate cache key based on parameters
        cache_key = f"{country}-{category}"
        cached_result = news_cache.get(cache_key)
        if cached_result:
            return cached_result

        # Construct the exact URL format
        base_url = "https://newsapi.org/v2/top-headlines"
        params = {
            'country': country,
            'category': category,
            'apiKey': '4cc3bf0cc5424522a615d94250eff225',
            'pageSize': 5  # Limit number of articles
        }

        response = requests.get(
            base_url,
            params=params,
            timeout=15,
            headers={'User-Agent': 'ChatbotApp/1.0'}
        )
        response.raise_for_status()
        
        articles = response.json().get('articles', [])
        if not articles:
            return f"No news articles found for {category} in {country.upper()}."

        # Format results
        news_results = [f"📰 *Latest {category.capitalize()} News from {country.upper()}:*\n"]
        
        for article in articles:
            news_results.append(
                f"• *{article.get('title', 'No Title')}*\n"
                f"  Published: {article.get('publishedAt', '')[:10]}\n"
                f"  {article.get('description', 'No description available.')}\n"
                f"  [Read more]({article.get('url', '#')})\n"
            )

        result = '\n'.join(news_results)
        news_cache.set(cache_key, result)
        return result

    except requests.RequestException as e:
        logger.error(f"News API request failed: {str(e)}")
        return "Sorry, I couldn't fetch the news at the moment. Please try again later."
    except Exception as e:
        logger.error(f"Unexpected error in fetch_news: {str(e)}")
        return "An unexpected error occurred while fetching news."
    try:
        # Generate cache key based on parameters
        cache_key = f"{category}-{query}-{country}"
        cached_result = news_cache.get(cache_key)
        if cached_result:
            return cached_result

        api_key = os.getenv('NEWS_API_KEY')
        base_url = "https://newsapi.org/v2"
        
        # Determine which endpoint to use
        if category or country:
            endpoint = f"{base_url}/top-headlines"
            params = {
                'apiKey': api_key,
                'pageSize': 5
            }
            if category:
                params['category'] = category
            if country:
                params['country'] = country
        else:
            endpoint = f"{base_url}/everything"
            params = {
                'apiKey': api_key,
                'pageSize': 5,
                'sortBy': 'publishedAt',
                'language': 'en'
            }
        
        if query:
            params['q'] = query

        response = requests.get(
            endpoint,
            params=params,
            timeout=15,
            headers={'User-Agent': 'ChatbotApp/1.0'}
        )
        response.raise_for_status()
        
        articles = response.json().get('articles', [])
        if not articles:
            return "No news articles found matching your criteria."

        # Format results
        news_results = [f"📰 *Latest News{f' about {query}' if query else ''}"
                       f"{f' in {category}' if category else ''}"
                       f"{f' from {country.upper()}' if country else ''}:*\n"]
        
        for article in articles:
            news_results.append(
                f"• *{article.get('title', 'No Title')}*\n"
                f"  Published: {article.get('publishedAt', '')[:10]}\n"
                f"  {article.get('description', 'No description available.')}\n"
                f"  [Read more]({article.get('url', '#')})\n"
            )

        result = '\n'.join(news_results)
        news_cache.set(cache_key, result)
        return result

    except requests.RequestException as e:
        logger.error(f"News API request failed: {str(e)}")
        return "Sorry, I couldn't fetch the news at the moment. Please try again later."
    except Exception as e:
        logger.error(f"Unexpected error in fetch_news: {str(e)}")
        return "An unexpected error occurred while fetching news."
        
# Updated chat endpoint
@app.route('/chat', methods=['POST'])
@handle_errors
def chat():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        user_query = data.get('query', '').strip()
        if not user_query:
            return jsonify({"error": "Query is required"}), 400

        cleaned_query = preprocess_text(user_query)
        
        # Handle different query types
        if "news" in cleaned_query.lower():
            response = fetch_news()
            return jsonify({"response": response, "source": "news"})

        if "wikipedia" in cleaned_query.lower() or "wiki" in cleaned_query.lower():
            search_terms = cleaned_query.split()
            search_terms = [term for term in search_terms if term not in ['wikipedia', 'wiki']]
            if not search_terms:
                return jsonify({"error": "Please specify what you want to search for"}), 400
            topic = ' '.join(search_terms)
            response = fetch_from_wikipedia(topic)
            return jsonify({"response": response, "source": "wikipedia"})

        # Find best matching response from training data
        best_match = None
        max_similarity = 0
        
        for entry in training_data:
            similarity = len(set(preprocess_text(entry['query']).split()) & set(cleaned_query.split()))
            if similarity > max_similarity:
                max_similarity = similarity
                best_match = entry

        response = best_match['response'] if best_match else "I don't understand. Could you rephrase that?"
        
        return jsonify({
            "response": response,
            "source": "local",
            "confidence": max_similarity if best_match else 0
        })

    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

# Updated training endpoint
@app.route('/train', methods=['POST'])
@handle_errors
def train():
    try:
        new_data = request.get_json()
        if not new_data or 'query' not in new_data or 'response' not in new_data:
            return jsonify({"error": "Invalid training data format"}), 400

        if new_data.get('source') in ['wikipedia', 'news']:
            return jsonify({"error": "External data cannot be saved to training data"}), 400

        training_data.append(new_data)
        
        data_dir = 'lib/data'
        file_path = os.path.join(data_dir, 'training_data.json')
        
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(training_data, file, indent=4)

        logger.info(f"Added new training data: {new_data['query']}")
        return jsonify({"message": "Training data updated successfully"})

    except Exception as e:
        logger.error(f"Error in train endpoint: {str(e)}")
        return jsonify({"error": "Failed to update training data", "message": str(e)}), 500

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "training_data_size": len(training_data)
    })

if __name__ == '__main__':
    try:
        logger.info("Server starting on http://0.0.0.0:5000")
        if os.environ.get('FLASK_ENV') == 'development':
            app.run(host='0.0.0.0', port=5000, debug=True)
        else:
            serve(app, host='0.0.0.0', port=5000)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise