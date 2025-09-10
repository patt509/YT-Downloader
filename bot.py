import os
import logging   # For logging errors and info

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pytubefix import YouTube  # Pytube is currently broken, I'm using pytubefix instead

# Import handlers from handlers.py
from handlers import start, handle_link

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("No TOKEN found. Please set the TOKEN environment variable.")

def main ():
    # Create the Application and pass it to the bot
    print("Creating application...")
    # Builder for the application object
    application = Application.builder().token(TOKEN).build()

    # Handlers are imported from handlers.py
    # Handler for the /start command
    application.add_handler(CommandHandler("start", start))
    # Listen for text messages ONLY, that are not commands (~filters.COMMAND means NOT a command)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    # The bot uses polling to get updates from Telegram
    application.run_polling()

if __name__ == "__main__":
    main()