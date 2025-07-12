# SpotifyToYT

A Python application that converts Spotify playlists to YouTube Music and downloads audio files with complete metadata and artwork.

## Features

- 🎵 Export Spotify playlists to JSON
- 🔍 Find matching songs on YouTube Music
- ⬇️ Download high-quality audio files
- 🎨 Embed album artwork and metadata
- 🚀 Multi-threaded processing for speed
- 🖥️ GUI and CLI interfaces
- 📱 Cross-platform support

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the pipeline:**
   ```bash
   ./start.sh "My Playlist Name"
   # or
   ./start.sh https://open.spotify.com/playlist/...
   # or
   ./start.sh 1  # playlist index
   ```

3. **Use the GUI:**
   ```bash
   python3 gui.py
   ```

## Requirements

- Python 3.7+
- yt-dlp
- Spotify API credentials
- Required Python packages (see requirements.txt)

## Project Structure

- `start.sh` - Main pipeline script
- `gui.py` - Graphical user interface
- `spoty_exporter_MK1.py` - Spotify playlist exporter
- `yt_searchtMK1.py` - YouTube Music search
- `yt_FetchMK1.py` - Audio downloader with metadata
- `.lib/` - Shared utilities and modules

## Configuration

1. Set up Spotify API credentials
2. Configure YouTube Music access (optional OAuth)
3. Run the setup scripts as needed

## Output

- `out/` - JSON playlist exports
- `songs/` - Downloaded audio files with metadata
- `logs/` - Application logs

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]