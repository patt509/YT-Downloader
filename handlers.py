import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from pytubefix import YouTube
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
MAX_VIDEO_DURATION = 10 * 60  # 10 minutes in seconds
MAX_PROCESSING_TIME = 5 * 60  # 5 minutes in seconds

# Helper function to send easter egg message
async def _send_easter_egg(user, context, chat_id):
    """Send easter egg message if user is in the special users list"""
    easter_egg_users = {
        user_name.strip(): msg.strip() for user_name, msg in zip(
            os.getenv('EASTER_EGG_USERS', '').split(','),
            os.getenv('EASTER_EGG_MESSAGES', '').split(',')
        ) if user_name.strip() and msg.strip()
    }
    
    if user.username in easter_egg_users:
        await context.bot.send_message(chat_id, easter_egg_users[user.username])

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

    if "youtube.com/" not in url and "youtu.be/" not in url and "music.youtube.com/" not in url:
        await update.message.reply_text("Please send a valid YouTube or Youtube Music link.")
        return
    
    # If it's YouTube Music, download MP3 directly
    if "music.youtube.com/" in url:
        await download_audio(update, context, url)
        return
    
    # If it's normal YouTube video/shorts, check duration first
    if "youtube.com/" in url or "youtu.be/" in url:
        # Check video duration before showing buttons
        try:
            yt = YouTube(url, use_oauth=False, allow_oauth_cache=True)
            if yt.length > MAX_VIDEO_DURATION:
                minutes = yt.length // 60
                seconds = yt.length % 60
                await update.message.reply_text(
                    f"❌ Video too long: {minutes}:{seconds:02d}\n"
                    f"Maximum duration allowed: {MAX_VIDEO_DURATION // 60} minutes"
                )
                return
        except Exception as e:
            print(f"Error checking video duration: {e}")
            await update.message.reply_text("Error accessing video. Please check if the link is valid and public.")
            return
        
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

# Download audio function with timeout
async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    # Determine if it's a callback or normal message
    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
        waiting_message = await context.bot.send_message(chat_id, "Processing audio download, please wait...")
        user = update.callback_query.from_user
    else:
        waiting_message = await update.message.reply_text("Processing audio download, please wait...")
        chat_id = update.message.chat_id
        user = update.effective_user

    file_path = None
    new_file_path = None
    
    try:
        # Wrap the entire download and send process in asyncio.wait_for for timeout
        await asyncio.wait_for(
            _download_and_send_audio(url, chat_id, waiting_message, context, user),
            timeout=MAX_PROCESSING_TIME
        )
    except asyncio.TimeoutError:
        print(f"Audio download timed out after {MAX_PROCESSING_TIME} seconds")
        await waiting_message.edit_text("⏰ Download timed out. The process took too long.")
        # Clean up any files that might have been created
        await _cleanup_files(file_path, new_file_path)
    except Exception as e:
        print(f"Error during audio download: {e}")
        await waiting_message.edit_text("An error occurred while downloading the audio. Please try again.")
        await _cleanup_files(file_path, new_file_path)

# Helper function for audio download and send
async def _download_and_send_audio(url: str, chat_id: int, waiting_message, context, user):
    file_path = None
    new_file_path = None
    
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
            
            # Send easter egg message after successful download
            await _send_easter_egg(user, context, chat_id)
            
        except Exception as send_error:
            print(f"Error sending audio: {send_error}")
            await waiting_message.edit_text("Audio downloaded but failed to send. Please try again.")
        finally:
            # Always clean up the file
            if os.path.exists(new_file_path):
                os.remove(new_file_path)
                
    except Exception as e:
        # Clean up any partial downloads
        await _cleanup_files(file_path, new_file_path)
        raise e

# Download video function with timeout
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    # Determine if it's a callback or normal message
    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
        waiting_message = await context.bot.send_message(chat_id, "Processing video download, please wait...")
        user = update.callback_query.from_user
    else:
        waiting_message = await update.message.reply_text("Processing video download, please wait...")
        chat_id = update.message.chat_id
        user = update.effective_user

    file_path = None
    
    try:
        # Wrap the entire download and send process in asyncio.wait_for for timeout
        await asyncio.wait_for(
            _download_and_send_video(url, chat_id, waiting_message, context, user),
            timeout=MAX_PROCESSING_TIME
        )
    except asyncio.TimeoutError:
        print(f"Video download timed out after {MAX_PROCESSING_TIME} seconds")
        await waiting_message.edit_text("⏰ Download timed out. The process took too long.")
        # Clean up any files that might have been created
        await _cleanup_files(file_path, None)
    except Exception as e:
        print(f"Error during video download: {e}")
        await waiting_message.edit_text("An error occurred while downloading the video. Please try again.")
        await _cleanup_files(file_path, None)

# Helper function for video download and send
async def _download_and_send_video(url: str, chat_id: int, waiting_message, context, user):
    file_path = None
    
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
            
            # Send easter egg message after successful download
            await _send_easter_egg(user, context, chat_id)
            
        except Exception as send_error:
            print(f"Error sending video: {send_error}")
            await waiting_message.edit_text("Video downloaded but failed to send. Please try again.")
        finally:
            # Always clean up the file
            if os.path.exists(file_path):
                os.remove(file_path)
                
    except Exception as e:
        # Clean up any partial downloads
        await _cleanup_files(file_path, None)
        raise e

# Helper function to clean up files
async def _cleanup_files(file_path: str = None, new_file_path: str = None):
    """Clean up downloaded files"""
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"Cleaned up file: {file_path}")
        except Exception as e:
            print(f"Error cleaning up file {file_path}: {e}")
    
    if new_file_path and os.path.exists(new_file_path):
        try:
            os.remove(new_file_path)
            print(f"Cleaned up file: {new_file_path}")
        except Exception as e:
            print(f"Error cleaning up file {new_file_path}: {e}")
