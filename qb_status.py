import qbittorrentapi
import aiohttp
import asyncio
import time
import os
import psutil
import json
from collections import deque

# Load configuration from an external JSON file to keep credentials and settings separate from the script
CONFIG_FILE = "/app/config.json"

CHECK_INTERVAL = 300  # Time interval (in seconds) between each torrent check cycle

def load_config():
    """Loads the configuration file containing connection details. If the file is missing or invalid, it exits."""
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Configuration file not found! Make sure config.json exists.")
        exit(1)
    except json.JSONDecodeError:
        print("Error parsing configuration file. Ensure the JSON is correctly formatted.")
        exit(1)

# Load configuration into a dictionary
config = load_config()

# Centralized host IP to avoid repetition across services
HOST = config["HOST"]

# qBittorrent connection details
QB_HOST = f"http://{HOST}:{config['QB_PORT']}"
QB_USERNAME = config["QB_USERNAME"]
QB_PASSWORD = config["QB_PASSWORD"]

# Sonarr and Radarr details (to trigger searches when necessary)
SONARR_HOST = f"http://{HOST}:{config['SONARR_PORT']}"
SONARR_API_KEY = config["SONARR_API_KEY"]
RADARR_HOST = f"http://{HOST}:{config['RADARR_PORT']}"
RADARR_API_KEY = config["RADARR_API_KEY"]

# Minimum time (in seconds) a torrent must be stalled before deletion is considered
TIME_THRESHOLD = 5 * 60

# File to store the total number of deleted torrents (for tracking purposes)
DELETE_COUNT_FILE = "/app/deleted_count.txt"
BATCH_SIZE = 5  # Number of torrents to delete at once for efficiency
DELETION_QUEUE = deque()  # Queue of torrents waiting for deletion
SONARR_TRIGGER = False  # Tracks whether Sonarr should be triggered
RADARR_TRIGGER = False  # Tracks whether Radarr should be triggered

def get_deleted_count():
    """Reads and returns the number of torrents deleted so far. Defaults to zero if the file is missing or unreadable."""
    try:
        with open(DELETE_COUNT_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0

def update_deleted_count(new_deletions):
    """Updates the file with the latest number of deleted torrents."""
    total_deleted = get_deleted_count() + new_deletions
    with open(DELETE_COUNT_FILE, "w") as f:
        f.write(str(total_deleted))
    return total_deleted

def system_under_load():
    """Checks CPU I/O wait. If it's too high, delays deletion to prevent system overload."""
    load = psutil.cpu_times_percent(interval=0, percpu=False)  # Non-blocking CPU load check
    return load.iowait > 10  # If I/O wait is over 10%, defer deletions

async def fetch_status(session, host, api_key, app_name):
    """Contacts Sonarr or Radarr to check if they are running and accessible."""
    headers = {"X-Api-Key": api_key}
    try:
        async with session.get(f"{host}/api/v3/system/status", headers=headers, timeout=2) as response:
            if response.status == 200:
                print(f"Successfully connected to {app_name}.")
    except Exception as e:
        print(f"Error connecting to {app_name}: {e}")

async def trigger_search(session, api_host, api_key, app_name):
    """Triggers a search in Sonarr or Radarr to replace missing content after deletion."""
    headers = {"X-Api-Key": api_key}
    search_endpoint = f"{api_host}/api/v3/command"
    payload = {"name": "MissingEpisodeSearch"} if "sonarr" in api_host else {"name": "missingMoviesSearch"}
    try:
        async with session.post(search_endpoint, headers=headers, json=payload, timeout=2) as response:
            if response.status == 201:
                print(f"Triggered search for missing files in {app_name}.")
    except Exception as e:
        print(f"Error triggering search in {app_name}: {e}")

async def process_deletions():
    """Handles the deletion of stalled torrents in batches. If system load is high, waits before retrying."""
    global SONARR_TRIGGER, RADARR_TRIGGER
    while DELETION_QUEUE:
        if system_under_load():
            print("System under high load. Pausing deletions.")
            await asyncio.sleep(5)  # Adaptive backoff
            continue
        
        batch = [DELETION_QUEUE.popleft() for _ in range(min(BATCH_SIZE, len(DELETION_QUEUE)))]
        client.torrents_delete(delete_files=True, torrent_hashes=[t.hash for t in batch])
        update_deleted_count(len(batch))  # Update total deletions
        print(f"Deleted {len(batch)} torrents. Remaining: {len(DELETION_QUEUE)}")
        
        for t in batch:
            if "sonarr" in t.category.lower():
                SONARR_TRIGGER = True
            elif "radarr" in t.category.lower():
                RADARR_TRIGGER = True
        
        await asyncio.sleep(1)  # Reduce disk I/O wait

async def monitor_torrents():
    """Continuously monitors qBittorrent for stalled torrents and queues them for deletion."""
    global SONARR_TRIGGER, RADARR_TRIGGER
    while True:
        try:
            client = qbittorrentapi.Client(host=QB_HOST, username=QB_USERNAME, password=QB_PASSWORD)
            print("Successfully connected to qBittorrent.")
            
            current_time = time.time()
            torrents = client.torrents_info(status_filter="stalled", fields=["hash", "num_seeds", "added_on", "category"])
            DELETION_QUEUE.clear()
            for torrent in torrents:
                if (current_time - torrent.added_on) >= TIME_THRESHOLD and torrent.num_seeds == 0:
                    DELETION_QUEUE.append(torrent)
            
            if not DELETION_QUEUE:
                print("No eligible stalled torrents found for deletion.")
            else:
                print(f"Processing {len(DELETION_QUEUE)} torrents for deletion...")
                await process_deletions()
        except Exception as e:
            print(f"Error connecting to qBittorrent: {e}")
        
        await asyncio.sleep(CHECK_INTERVAL)  # Wait before checking again

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [
            monitor_torrents(),
            fetch_status(session, SONARR_HOST, SONARR_API_KEY, "Sonarr"),
            fetch_status(session, RADARR_HOST, RADARR_API_KEY, "Radarr")
        ]
        if SONARR_TRIGGER:
            tasks.append(trigger_search(session, SONARR_HOST, SONARR_API_KEY, "Sonarr"))
        if RADARR_TRIGGER:
            tasks.append(trigger_search(session, RADARR_HOST, RADARR_API_KEY, "Radarr"))
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
