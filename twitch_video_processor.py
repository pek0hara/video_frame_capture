#!/usr/bin/env python3
import os
import subprocess
import logging
import json
import requests # For Twitch API calls
from datetime import datetime

# --- Configuration ---
TWITCH_STREAMER_USERNAME = "YOUR_STREAMER_USERNAME_HERE"
OUTPUT_DIRECTORY = "twitch_clips"
PROCESSED_VIDEOS_FILE = "processed_videos.txt"
LOG_FILE = "twitch_processor.log"
TWITCH_CLIENT_ID = "YOUR_TWITCH_CLIENT_ID"
TWITCH_APP_ACCESS_TOKEN = "YOUR_TWITCH_APP_ACCESS_TOKEN"
FFMPEG_PATH = "ffmpeg"
YT_DLP_PATH = "yt-dlp"

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logging.info("Script starting...") # Initial log to confirm script execution and logging setup

# --- Helper Functions ---
def ensure_dir(directory_path):
    """Ensures that a directory exists, creating it if necessary."""
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
        logging.info(f"Created directory: {directory_path}")

def load_processed_videos():
    """Loads the set of processed video IDs from the tracking file."""
    processed_videos_dir = os.path.dirname(PROCESSED_VIDEOS_FILE)
    if processed_videos_dir and not os.path.exists(processed_videos_dir):
        ensure_dir(processed_videos_dir)
    if not os.path.exists(PROCESSED_VIDEOS_FILE):
        with open(PROCESSED_VIDEOS_FILE, "w") as f:
            pass
        return set()
    with open(PROCESSED_VIDEOS_FILE, "r") as f:
        return set(line.strip() for line in f)

def save_processed_video(video_id):
    """Adds a video ID to the tracking file."""
    with open(PROCESSED_VIDEOS_FILE, "a") as f:
        f.write(str(video_id) + "\n")

# --- Main Application Logic ---
def get_twitch_user_id(username):
    """Gets the Twitch User ID for a given username."""
    if not TWITCH_CLIENT_ID or TWITCH_CLIENT_ID == "YOUR_TWITCH_CLIENT_ID" or \
       not TWITCH_APP_ACCESS_TOKEN or TWITCH_APP_ACCESS_TOKEN == "YOUR_TWITCH_APP_ACCESS_TOKEN":
        logging.error("Twitch Client ID or App Access Token is not configured correctly in the script.")
        return None
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {TWITCH_APP_ACCESS_TOKEN}"
    }
    url = f"https://api.twitch.tv/helix/users?login={username}"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if data.get("data"):
            return data["data"][0]["id"]
        else:
            logging.error(f"Twitch user '{username}' not found or unexpected API response: {data}")
            return None
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error fetching Twitch user ID for '{username}': {http_err}")
        if http_err.response is not None: logging.error(f"Response content: {http_err.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error fetching Twitch user ID for '{username}': {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON response from Twitch API (users) for '{username}': {e}")
        return None

def get_new_videos(user_id, processed_videos):
    """Fetches recent videos for a user, filtering out processed ones."""
    if not user_id: return []
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {TWITCH_APP_ACCESS_TOKEN}"
    }
    url = f"https://api.twitch.tv/helix/videos?user_id={user_id}&type=archive&sort=time&first=5"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        videos_data = response.json().get("data", [])
        new_videos = []
        for video in videos_data:
            if video.get("id") and video["id"] not in processed_videos:
                new_videos.append({
                    "id": video["id"],
                    "title": video.get("title", "Untitled Video"),
                    "created_at": video.get("created_at"),
                    "url": video.get("url")
                })
        if new_videos:
             logging.info(f"Found {len(new_videos)} new video(s) for user ID {user_id}.")
        else:
            logging.info(f"No new videos found for user ID {user_id} (checked the latest 5 videos).")
        return new_videos
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error fetching videos for user ID {user_id}: {http_err}")
        if http_err.response is not None: logging.error(f"Response content: {http_err.response.text}")
        return []
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error fetching videos for user ID {user_id}: {e}")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON response from Twitch API (videos) for user ID {user_id}: {e}")
        return []
    except KeyError as e:
        logging.error(f"Unexpected API response structure (videos) (KeyError: {e}).")
        return []

def download_video(video_id, download_path):
    """Downloads a video using yt-dlp given its Twitch video ID."""
    ensure_dir(download_path)
    video_file_template = os.path.join(download_path, f"{video_id}.%(ext)s")
    logging.info(f"Attempting to download video {video_id} using yt-dlp to template {video_file_template}")
    try:
        command = [
            YT_DLP_PATH,
            "-o", video_file_template,
            "--no-playlist",
            "--restrict-filenames",
            f"https://www.twitch.tv/videos/{video_id}"
        ]
        process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        logging.debug(f"yt-dlp stdout for {video_id}: {process.stdout}")
        for item in os.listdir(download_path):
            if item.startswith(video_id):
                downloaded_video_path = os.path.join(download_path, item)
                logging.info(f"Video {video_id} successfully downloaded to {downloaded_video_path}")
                return downloaded_video_path
        logging.error(f"yt-dlp command succeeded for {video_id} but could not find downloaded file in {download_path} starting with '{video_id}'.")
        return None
    except subprocess.CalledProcessError as e:
        logging.error(f"yt-dlp error downloading video {video_id}. Return code: {e.returncode}")
        logging.error(f"yt-dlp stderr: {e.stderr}")
        return None
    except FileNotFoundError:
        logging.error(f"'{YT_DLP_PATH}' command not found. Ensure yt-dlp is installed and in PATH.")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during video download for {video_id}: {e}")
        return None

def extract_frames(video_path, video_id, base_output_dir):
    """Extracts frames every 2 seconds from a video using FFmpeg."""
    if not video_path or not os.path.exists(video_path):
        logging.error(f"Video file not found or not provided for frame extraction: {video_path}")
        return False
    video_frames_output_dir = os.path.join(base_output_dir, video_id)
    ensure_dir(video_frames_output_dir)
    logging.info(f"Extracting frames from {video_path} into {video_frames_output_dir}")
    try:
        command = [
            FFMPEG_PATH,
            "-i", video_path,
            "-vf", "fps=1/2",
            os.path.join(video_frames_output_dir, f"{video_id}_frame_%06d.jpg"),
            "-hide_banner"
        ]
        process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        logging.info(f"Successfully extracted frames for video {video_id} into {video_frames_output_dir}")
        logging.debug(f"FFmpeg stdout for {video_id}: {process.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"FFmpeg error extracting frames for video {video_id}. Return code: {e.returncode}")
        logging.error(f"FFmpeg stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        logging.error(f"'{FFMPEG_PATH}' command not found. Ensure FFmpeg is installed and in PATH.")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred during frame extraction for {video_id}: {e}")
        return False

def main():
    """Main function to orchestrate the video processing."""
    logging.info("Starting Twitch video processor script...")
    ensure_dir(OUTPUT_DIRECTORY)
    if TWITCH_STREAMER_USERNAME == "YOUR_STREAMER_USERNAME_HERE" or \
       TWITCH_CLIENT_ID == "YOUR_TWITCH_CLIENT_ID" or \
       TWITCH_APP_ACCESS_TOKEN == "YOUR_TWITCH_APP_ACCESS_TOKEN":
        logging.error("CRITICAL CONFIGURATION ERROR: Twitch streamer username or API credentials are placeholders.")
        logging.error("Please update TWITCH_STREAMER_USERNAME, TWITCH_CLIENT_ID, and TWITCH_APP_ACCESS_TOKEN in the script.")
        return
    processed_video_ids = load_processed_videos()
    user_id = get_twitch_user_id(TWITCH_STREAMER_USERNAME)
    if not user_id:
        logging.warning(f"Could not retrieve Twitch User ID for '{TWITCH_STREAMER_USERNAME}'. Cannot proceed.")
        return
    new_videos = get_new_videos(user_id, processed_video_ids)
    if not new_videos:
        logging.info("No new videos found to process at this time.")
        return
    temp_download_dir = os.path.join(OUTPUT_DIRECTORY, "temp_downloads")
    ensure_dir(temp_download_dir)
    success_count = 0
    failure_count = 0
    for video_info in new_videos:
        video_id = video_info["id"]
        video_title = video_info.get("title", "N/A")
        logging.info(f"Processing new video: ID='{video_id}', Title='{video_title}'")
        downloaded_video_path = download_video(video_id, temp_download_dir)
        if downloaded_video_path:
            if extract_frames(downloaded_video_path, video_id, OUTPUT_DIRECTORY):
                save_processed_video(video_id)
                logging.info(f"Successfully processed video {video_id} ('{video_title}').")
                success_count += 1
                try:
                    os.remove(downloaded_video_path)
                    logging.info(f"Removed temporary video file: {downloaded_video_path}")
                except OSError as e:
                    logging.error(f"Error deleting temporary video file {downloaded_video_path}: {e}")
            else:
                logging.error(f"Failed to extract frames for video {video_id} ('{video_title}'). Will be re-attempted next run unless manually added to {PROCESSED_VIDEOS_FILE}.")
                failure_count +=1
        else:
            logging.error(f"Failed to download video {video_id} ('{video_title}'). Will be re-attempted next run.")
            failure_count +=1
    logging.info(f"Twitch video processor finished. Successfully processed: {success_count} new video(s). Failed attempts: {failure_count} video(s).")

if __name__ == "__main__":
    ensure_dir(OUTPUT_DIRECTORY) # Ensure output directory exists at script start
    load_processed_videos() # Ensure processed videos file exists and is loadable
    main()
