import os
import threading
from dotenv import load_dotenv
from web import app
from bot import bot

load_dotenv()

def run_flask():
    # Render provides a PORT environment variable dynamically
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Start Flask in a background thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Start the Discord Bot in the main thread
    token = os.getenv("DISCORD_TOKEN")
    bot.run(token)
