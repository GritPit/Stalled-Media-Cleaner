# qBittorrent Cleanup Script

So, you want to automate the cleanup of stalled torrents and keep your Sonarr/Radarr library in check without lifting a finger? You've come to the right place. This script does all the heavy lifting by:
- Detecting stalled torrents in qBittorrent
- Deleting them after a set period (5 minutes by default)
- Telling Sonarr and Radarr to go find replacements
- Running on a loop so you never have to think about it again

## What You'll Need
Before you get this up and running, make sure you have:
- **Docker & Docker Compose** installed
- A running instance of **qBittorrent, Sonarr, and Radarr**
- Python 3.11+ if you want to run it manually

## File Structure
Set up your project directory like this:
```
/qbittorrent-cleanup
├── docker-compose.yml   # Docker Compose setup
├── Dockerfile           # Docker image build instructions
├── config.json          # Stores qBittorrent, Sonarr, and Radarr connection details
├── deleted_count.txt    # Keeps track of how many torrents were deleted
├── qb_status.py         # The script that does all the magic
├── requirements.txt     # Python dependencies
```

## Configuration File (config.json)
You'll need to create a `config.json` file with your qBittorrent, Sonarr, and Radarr details:
```json
{
    "HOST": "IP_ADDRESS",
    "QB_PORT": QB_PORT,
    "QB_USERNAME": "USER_NAME",
    "QB_PASSWORD": "PASSWORD",
    "SONARR_PORT": SONARR_PORT,
    "SONARR_API_KEY": "SONARR_API_KEY",
    "RADARR_PORT": RADARR_PORT,
    "RADARR_API_KEY": "RADARR_API_KEY"
}
```

## Running with Docker Compose
1. **Make sure your `config.json` file is in place**
2. **Build and start the container**:
   ```sh
   docker compose up -d --build
   ```
3. **Check logs to see if it's working**:
   ```sh
   docker logs qbittorrent-cleanup -f
   ```

## Running Manually (Without Docker)
If you're not into Docker, you can run this directly:
```sh
pip install -r requirements.txt
python qb_status.py
```

## Stopping the Script
If you're running it in Docker:
```sh
docker compose down
```

If you're running it manually, just hit **Ctrl + C**.

## Troubleshooting
### Issue: "No eligible stalled torrents found for deletion."
This just means no torrents meet the deletion criteria. If you think some should be deleted, check that:
- The torrents have been stalled for more than 5 minutes
- They have **zero seeds**

### Issue: "Error connecting to qBittorrent/Sonarr/Radarr"
- Double-check your `config.json` for typos
- Ensure your services are actually running and accessible from the script

## Final Thoughts
This setup should keep your qBittorrent nice and tidy while ensuring Sonarr and Radarr fill in the gaps. If something breaks, well, it's probably your fault. But hey, at least now you know where to look! Happy automating.
