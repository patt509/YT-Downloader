import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from pytubefix import YouTube
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Message handler for the /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! Send me a YouTube or Youtube Music link and I'll download the video or song for you."
    )
    
# Message handler for processing YouTube links
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Grab the content of the last message sent to the bot
    url = update.message.text
    user = update.effective_user

    # Easter egg for specific users
    easter_egg_users = {
        user.strip(): msg.strip() for user, msg in zip(
            os.getenv('EASTER_EGG_USERS', '').split(','),
            os.getenv('EASTER_EGG_MESSAGES', '').split(',')
        ) if user.strip() and msg.strip()
    }
    
    if user.username in easter_egg_users:
        await update.message.reply_text(easter_egg_users[user.username])

    if "youtube.com/" not in url and "youtu.be/" not in url and "music.youtube.com/" not in url:
        await update.message.reply_text("Please send a valid YouTube or Youtube Music link.")
        return
    
    # If it's YouTube Music, download MP3 directly
    if "music.youtube.com/" in url:
        await download_audio(update, context, url)
        return
    
    # If it's normal YouTube video/shorts, show buttons
    if "youtube.com/" in url or "youtu.be/" in url:
        keyboard = [
            [InlineKeyboardButton("🎵 MP3 (Audio)", callback_data=f"mp3:{url}")],
            [InlineKeyboardButton("🎬 MP4 (Video)", callback_data=f"mp4:{url}")]
        ]
        # Set up the reply markup with the just created keyboard
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Choose download format:", 
            reply_markup=reply_markup
        )

# Callback handler for buttons
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action, url = query.data.split(":", 1)
    
    if action == "mp3":
        await download_audio(update, context, url)
    elif action == "mp4":
        await download_video(update, context, url)

# Download audio function
async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    # Determine if it's a callback or normal message
    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
        waiting_message = await context.bot.send_message(chat_id, "Processing audio download, please wait...")
    else:
        waiting_message = await update.message.reply_text("Processing audio download, please wait...")
        chat_id = update.message.chat_id

    try:
        yt = YouTube(url, use_oauth=False, allow_oauth_cache=True)
        audio_stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
        
        if not audio_stream:
            await waiting_message.edit_text("No audio stream available for this video.")
            return
            
        file_path = audio_stream.download()
        base, ext = os.path.splitext(file_path)
        new_file_path = base + ".mp3"
        os.rename(file_path, new_file_path)

        # Open file, send it, then ensure it's closed
        try:
            with open(new_file_path, 'rb') as audio_file:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    title=yt.title,
                    duration=yt.length,
                    read_timeout=300,  # 5 minutes timeout
                    write_timeout=300
                )
            await waiting_message.delete()
        except Exception as send_error:
            print(f"Error sending audio: {send_error}")
            await waiting_message.edit_text("Audio downloaded but failed to send. Please try again.")
        finally:
            # Always clean up the file
            if os.path.exists(new_file_path):
                os.remove(new_file_path)

    except Exception as e:
        print(f"Error during audio download: {e}")
        await waiting_message.edit_text("An error occurred while downloading the audio. Please try again.")
        # Clean up any partial download
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        if 'new_file_path' in locals() and os.path.exists(new_file_path):
            os.remove(new_file_path)

# Download video function
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    # Determine if it's a callback or normal message
    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
        waiting_message = await context.bot.send_message(chat_id, "Processing video download, please wait...")
    else:
        waiting_message = await update.message.reply_text("Processing video download, please wait...")
        chat_id = update.message.chat_id

    try:
        yt = YouTube(url, use_oauth=False, allow_oauth_cache=True)
        video_stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        
        if not video_stream:
            await waiting_message.edit_text("No video stream available for this video.")
            return
            
        file_path = video_stream.download()

        # Open file, send it, then ensure it's closed
        try:
            with open(file_path, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=video_file,
                    caption=yt.title,
                    duration=yt.length,
                    read_timeout=300,  # 5 minutes timeout
                    write_timeout=300
                )
            await waiting_message.delete()
        except Exception as send_error:
            print(f"Error sending video: {send_error}")
            await waiting_message.edit_text("Video downloaded but failed to send. Please try again.")
        finally:
            # Always clean up the file
            if os.path.exists(file_path):
                os.remove(file_path)

    except Exception as e:
        print(f"Error during video download: {e}")
        await waiting_message.edit_text("An error occurred while downloading the video. Please try again.")
        # Clean up any partial download
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)