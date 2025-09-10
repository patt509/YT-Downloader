import os
from telegram import Update
from telegram.ext import ContextTypes
from pytubefix import YouTube

# Message handler for the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! Send me a YouTube or Youtube Music link and I'll download the video or song for you."
    )
    
# Message handler for processing YouTube links
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Grab the content of the last message sent to the bot
    url = update.message.text

    if "youtube.com/" not in url and "youtu.be/" not in url and "music.youtube.com/" not in url:
        await update.message.reply_text("Please send a valid YouTube or Youtube Music link.")
        return
    
    waiting_message = await update.message.reply_text("Processing your link, please wait...")

    try:
        yt = YouTube(url, use_oauth=False, allow_oauth_cache=True)
        # Check if it's a music link
        audio_stream = yt.streams.filter(only_audio=True).first()
        
        if not audio_stream:
            await waiting_message.edit_text("No audio stream available for this video.")
            return
            
        # Download the audio stream, returns the file path string
        file_path = audio_stream.download()

        # Split the file path string into base and extension
        base, ext = os.path.splitext(file_path)
        new_file_path = base + ".mp3"
        # Rename the file to have .mp3 extension
        os.rename(file_path, new_file_path)

        # Send the audio file to the user
        await context.bot.send_audio(
            # Specify to send the file to the chat where the message came from
            chat_id=update.message.chat_id,
            # Open the file in binary read mode ('rb'), used for non-text files
            audio = open(new_file_path, 'rb'),
            title = yt.title,
            duration = yt.length
        )

        os.remove(new_file_path)  # Clean up the file after sending
        await waiting_message.delete()  # Remove the waiting message

    except Exception as e:
        print(f"Error during download or send: {e}")
        await waiting_message.edit_text("An error occurred while processing your request. Be sure the video is public and try again.")