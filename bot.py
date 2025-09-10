import os
import logging   # For logging errors and info

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pytube import YouTube

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("No TOKEN found. Please set the TOKEN environment variable.")

# Message handler for the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! Send me a YouTube or Youtube Music link and I'll download the video or song for you."
   )

def main ():
    # Create the Application and pass it to the bot
    print("Creating application...")
    # Builder for the application object
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    # The bot uses polling to get updates from Telegram
    application.run_polling()

if __name__ == "__main__":
    main()