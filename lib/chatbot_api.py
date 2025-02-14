import speech_recognition as sr
import pyttsx3
import json
import re
import sys
import time
import os
import requests
import nltk
from textblob import TextBlob
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from datetime import datetime


# Download required NLTK resources
def download_nltk_resources():
    resources = ['punkt', 'stopwords', 'averaged_perceptron_tagger']
    for resource in resources:
        try:
            if resource == 'punkt':
                nltk.data.find(f'tokenizers/{resource}')
            else:
                nltk.data.find(f'corpora/{resource}')
        except LookupError:
            nltk.download(resource)

download_nltk_resources()

class VoiceChatbot:
    def __init__(self):
        # Initialize speech recognition
        self.recognizer = sr.Recognizer()

        # Initialize text-to-speech engine with female voice
        self.engine = pyttsx3.init()
        voices = self.engine.getProperty('voices')
        for voice in voices:
            if 'female' in voice.name.lower():
                self.engine.setProperty('voice', voice.id)
                break

        # Load training data
        self.training_data = self.load_training_data()

        # Initialize cache for API responses
        self.api_cache = {}

    def load_training_data(self):
        default_data = [
            {"query": "hello", "response": "Hi! How can I help you today?"},
            {"query": "how are you", "response": "I'm doing well, thank you for asking!"},
            {"query": "what is your name", "response": "I'm a voice chatbot assistant, nice to meet you!"},
            {"query": "goodbye", "response": "Goodbye! Have a great day!"},
            {"query": "thanks", "response": "You're welcome!"}
        ]

        try:
            os.makedirs('lib/data', exist_ok=True)
            file_path = 'lib/data/sample_data.json'

            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump(default_data, f, indent=4)
                return default_data

            with open(file_path, 'r') as f:     
                return json.load(f)
        except Exception as e:
            print(f"Error loading training data: {e}")
            return default_data

    def save_training_data(self):
        try:
            file_path = 'lib\data\sample_data.json'
            with open(file_path, 'w') as f:
                json.dump(self.training_data, f, indent=4)
            print(f"New response saved to: {file_path}")
        except Exception as e:
            print(f"Error saving training data: {e}")

    def preprocess_text(self, text):
        try:
            corrected_text = str(TextBlob(text).correct())
            cleaned_text = re.sub(r'[^a-zA-Z0-9\s]', '', corrected_text.lower())
            words = word_tokenize(cleaned_text)
            stop_words = set(stopwords.words('english'))
            filtered_words = [word for word in words if word not in stop_words]
            return ' '.join(filtered_words)
        except Exception as e:
            print(f"Error in text preprocessing: {e}")
            return text

    def fetch_news(self, url):
        if url in self.api_cache:
            return self.api_cache[url]

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                articles = data.get('articles', [])
                news_summaries = [article['title'] for article in articles[:5]]
                news_result = '\n'.join(news_summaries)
                self.api_cache[url] = news_result
                return news_result
            return "No news available right now."
        except Exception as e:
            print(f"Error fetching news: {e}")
            return "Sorry, I couldn't fetch the news right now."

    def speak(self, text):
        try:
            print(f"Bot: {text}")
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"Error in speech synthesis: {e}")

    def play_beep(self):
        """Plays a short beep sound before listening."""
        try:
            if os.name == 'nt':  # Windows
                import winsound
                winsound.Beep(1000, 300)  # Frequency: 1000Hz, Duration: 300ms
            else:  # Mac/Linux
                sys.stdout.write('\a')  # Terminal beep sound
                sys.stdout.flush()
        except Exception as e:
            print(f"Error playing beep sound: {e}")

    def listen(self):
        with sr.Microphone() as source:
            self.play_beep()  # Play the beep sound before listening
            print("\nListening...")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            try:
                audio = self.recognizer.listen(source, timeout=5)
                text = self.recognizer.recognize_google(audio)
                print(f"You said: {text}")
                return text
            except sr.WaitTimeoutError:
                self.speak("Sorry, I didn't hear anything. Please try again.")
                return None
            except sr.UnknownValueError:
                self.speak("Sorry, I didn't catch that. Could you please repeat?")
                return None
            except Exception as e:
                print(f"Error in speech recognition: {e}")
                self.speak("Sorry, there was an error understanding your speech.")
                return None

    def get_weather(self, city):
        """Fetch real-time weather details for a given city."""
        api_key = os.getenv("10c7044f2ad5a789668dfa1bf62a7ba9", "ca2a0c8d12743e7f48f12a7e480a6349")  # Replace with your actual OpenWeatherMap API key
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"

        if city in self.api_cache:  # Check cache to avoid redundant requests
            return self.api_cache[city]

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                weather_info = (
                    f"Current weather in {data['name']}:\n"
                    f"Temperature: {data['main']['temp']}°C\n"
                    f"Weather: {data['weather'][0]['description']}\n"
                    f"Humidity: {data['main']['humidity']}%\n"
                    f"Wind Speed: {data['wind']['speed']} m/s"
                )
                self.api_cache[city] = weather_info  # Cache result
                return weather_info
            return "Sorry, I couldn't get the weather details."
        except requests.exceptions.RequestException as e:
            print(f"Error fetching weather: {e}")
            return "Unable to fetch weather details at the moment."

    def get_time_and_date(self):
        """Fetch the current time and date."""
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        current_date = now.strftime("%Y-%m-%d")
        return f"The current time is {current_time} and the date is {current_date}."

    def process_query(self, query):
        if not query:
            return

        cleaned_query = self.preprocess_text(query)

        # Check for weather-related queries
        if "weather" in cleaned_query:
            match = re.search(r'weather in (\w+)', cleaned_query)
            if match:
                city = match.group(1)
                return self.get_weather(city)
            return "Please specify a city, like 'weather in New York'."

        # Check for time and date-related queries
        if "time" in cleaned_query or "date" in cleaned_query:
            return self.get_time_and_date()

        # Check for news-related queries
        if "business news" in cleaned_query:
            return self.fetch_news("https://newsapi.org/v2/top-headlines?country=us&category=business&apiKey=4cc3bf0cc5424522a615d94250eff225")
        elif "tech news" in cleaned_query:
            return self.fetch_news("https://newsapi.org/v2/top-headlines?sources=techcrunch&apiKey=4cc3bf0cc5424522a615d94250eff225")
        elif "domains" in cleaned_query:
            return self.fetch_news("https://newsapi.org/v2/everything?domains=wsj.com&apiKey=4cc3bf0cc5424522a615d94250eff225")
        elif "Apple" in cleaned_query:
            return self.fetch_news("https://newsapi.org/v2/everything?q=apple&from=2025-02-12&to=2025-02-12&sortBy=popularity&apiKey=4cc3bf0cc5424522a615d94250eff225")
        elif "Tesla" in cleaned_query:
            return self.fetch_news("https://newsapi.org/v2/everything?q=tesla&from=2025-01-13&sortBy=publishedAt&apiKey=4cc3bf0cc5424522a615d94250eff225")

        best_match = None
        max_intersection = 0
        query_words = set(cleaned_query.split())
        for entry in self.training_data:
            entry_words = set(self.preprocess_text(entry['query']).split())
            intersection = len(query_words.intersection(entry_words))
            if intersection > max_intersection:
                max_intersection = intersection
                best_match = entry

        if best_match:
            return best_match['response']
        else:
            self.speak("I don't know the answer to that. Can you give me the correct response?")
            new_response = self.listen()
            if new_response:
                self.training_data.append({"query": query, "response": new_response})
                self.save_training_data()
                return "Thank you! I've learned something new. ask another question in botany. "

        return "I'm not sure how to respond to that. Could you rephrase it?"

    def run(self):
        self.speak("Hello! I'm your voice assistant. How can I help you today?")

        while True:
            user_input = self.listen()
            if user_input:
                if any(word in user_input.lower() for word in ['quit', 'exit', 'goodbye', 'bye']):
                    self.speak("Goodbye! Have a great day!")
                    break

                response = self.process_query(user_input)
                self.speak(response)


if __name__ == "__main__":
    print("Starting Voice Chatbot...")
    print("Press Ctrl+C to exit")
    chatbot = VoiceChatbot()
    try:
        chatbot.run()
    except KeyboardInterrupt:
        print("\nExiting Voice Chatbot...")