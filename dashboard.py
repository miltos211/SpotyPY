import streamlit as st
import subprocess
import json
import os
import sys
import time
from pathlib import Path
import threading
import queue

def main():
    st.set_page_config(
        page_title="Spotify → YouTube Pipeline",
        page_icon="🎵",
        layout="wide"
    )
    
    st.title("🎵 Spotify to YouTube Music Pipeline")
    st.markdown("Convert your Spotify playlists to YouTube Music")
    
    # Sidebar for navigation
    st.sidebar.title("Pipeline Steps")
    step = st.sidebar.radio(
        "Choose a step:",
        [
            "1. Export Spotify Playlist",
            "2. Search YouTube Music", 
            "3. Download Audio Files",
            "4. Create YouTube Playlist"
        ]
    )
    
    if step == "1. Export Spotify Playlist":
        export_spotify_page()
    elif step == "2. Search YouTube Music":
        search_youtube_page()
    elif step == "3. Download Audio Files":
        download_audio_page()
    elif step == "4. Create YouTube Playlist":
        create_playlist_page()

def run_script_with_output(cmd, output_container):
    """Run a script and capture its output in real-time"""
    try:
        # Use the virtual environment's python
        venv_python = ".venv/bin/python"
        if os.path.exists(venv_python):
            # Replace 'python' with the venv python path
            if cmd[0] == "python":
                cmd[0] = venv_python
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        output_lines = []
        for line in iter(process.stdout.readline, ''):
            output_lines.append(line.rstrip())
            # Update the output container with latest lines
            output_container.text('\n'.join(output_lines[-20:]))  # Show last 20 lines
        
        process.wait()
        return process.returncode == 0, '\n'.join(output_lines)
    except Exception as e:
        return False, str(e)

def export_spotify_page():
    st.header("📱 Export Spotify Playlist")
    st.write("Extract tracks from your Spotify playlists")
    
    # First show list playlists option
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("List Your Playlists")
        if st.button("Show My Playlists"):
            with st.spinner("Fetching playlists..."):
                cmd = [".venv/bin/python", "spoty_exporter_MK1.py", "--list"]
                
                output_container = st.empty()
                success, output = run_script_with_output(cmd, output_container)
                
                if success:
                    st.success("✅ Playlists loaded!")
                    with st.expander("View playlists"):
                        st.text(output)
                else:
                    st.error("❌ Failed to fetch playlists")
                    st.text(output)
    
    with col2:
        st.subheader("Export Playlist")
        
        playlist_input = st.text_input(
            "Playlist (name, URL, ID, or number):",
            placeholder="My Playlist or https://open.spotify.com/playlist/..."
        )
        
        output_file = st.text_input(
            "Output JSON file:",
            value="out/playlist.json",
            placeholder="out/my_playlist.json"
        )
        
        if st.button("Export Playlist", type="primary"):
            if playlist_input and output_file:
                with st.spinner("Exporting playlist..."):
                    # Ensure output directory exists
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                    
                    cmd = [
                        ".venv/bin/python", "spoty_exporter_MK1.py",
                        "--playlist", playlist_input,
                        "--output", output_file
                    ]
                    
                    output_container = st.empty()
                    success, output = run_script_with_output(cmd, output_container)
                    
                    if success and os.path.exists(output_file):
                        st.success(f"✅ Exported playlist to {output_file}")
                        
                        # Show track count
                        try:
                            with open(output_file, 'r') as f:
                                data = json.load(f)
                            st.info(f"📊 Exported {len(data)} tracks - Ready for Step 2!")
                        except:
                            pass
                    else:
                        st.error("❌ Export failed")
                        with st.expander("View output"):
                            st.text(output)
            else:
                st.error("Please fill in all fields")

def search_youtube_page():
    st.header("🔍 Search YouTube Music")
    st.write("Find YouTube matches for your Spotify tracks")
    
    col1, col2 = st.columns(2)
    
    with col1:
        input_file = st.text_input(
            "Spotify JSON file:",
            value="out/playlist.json",
            help="JSON file from Step 1"
        )
        
        if input_file and os.path.exists(input_file):
            try:
                with open(input_file, 'r') as f:
                    data = json.load(f)
                st.success(f"✅ Found {len(data)} tracks")
                
                # Show sample tracks
                with st.expander("Preview tracks"):
                    for i, track in enumerate(data[:5], 1):
                        st.write(f"{i}. **{track.get('name', 'Unknown')}** by {', '.join(track.get('artists', ['Unknown']))}")
                    if len(data) > 5:
                        st.write(f"... and {len(data) - 5} more")
            except:
                st.error("Invalid JSON file")
        elif input_file:
            st.warning("File not found")
    
    with col2:
        st.subheader("Search Settings")
        
        thread_count = st.slider(
            "Concurrent searches:",
            min_value=1,
            max_value=8,
            value=3,
            help="More threads = faster but more API calls"
        )
        
        output_file = st.text_input(
            "Output filename:",
            value="out/enriched_output.json"
        )
        
        if st.button("Start YouTube Search", type="primary"):
            if input_file and os.path.exists(input_file):
                with st.spinner(f"Searching YouTube Music with {thread_count} threads..."):
                    # Ensure output directory exists
                    os.makedirs(os.path.dirname(output_file), exist_ok=True)
                    
                    cmd = [
                        ".venv/bin/python", "yt_searchtMK1.py",
                        "--input", input_file,
                        "--output", output_file,
                        "--threads", str(thread_count)
                    ]
                    
                    output_container = st.empty()
                    success, output = run_script_with_output(cmd, output_container)
                    
                    if success and os.path.exists(output_file):
                        st.success(f"✅ Created {output_file}")
                        st.info("Ready for Step 3: Download Audio")
                        
                        # Show success rate
                        try:
                            with open(output_file, 'r') as f:
                                enriched = json.load(f)
                            found = sum(1 for t in enriched if t.get('youtube'))
                            rate = (found / len(enriched)) * 100
                            st.metric("Success Rate", f"{rate:.1f}%", f"{found}/{len(enriched)} found")
                        except:
                            pass
                    else:
                        st.error("❌ Search failed")
                        with st.expander("View output"):
                            st.text(output)
            else:
                st.error("Please provide a valid input file")

def download_audio_page():
    st.header("⬇️ Download Audio Files")
    st.write("Download MP3 files from YouTube")
    
    col1, col2 = st.columns(2)
    
    with col1:
        input_file = st.text_input(
            "Enriched JSON file:",
            value="out/enriched_output.json",
            help="JSON file from Step 2"
        )
        
        if input_file and os.path.exists(input_file):
            try:
                with open(input_file, 'r') as f:
                    data = json.load(f)
                valid_tracks = [t for t in data if t.get('youtube')]
                st.success(f"✅ Found {len(data)} tracks ({len(valid_tracks)} with YouTube matches)")
            except:
                st.error("Invalid JSON file")
        elif input_file:
            st.warning("File not found")
    
    with col2:
        st.subheader("Download Settings")
        
        output_dir = st.text_input(
            "Output directory:",
            value="downloads/",
            help="Where to save MP3 files"
        )
        
        download_threads = st.slider(
            "Concurrent downloads:",
            min_value=1,
            max_value=8,
            value=3
        )
        
        if st.button("Start Downloads", type="primary"):
            if input_file and os.path.exists(input_file):
                with st.spinner("Downloading tracks..."):
                    # Ensure output directory exists
                    os.makedirs(output_dir, exist_ok=True)
                    
                    cmd = [
                        ".venv/bin/python", "yt_FetchMK1.py",
                        "--input", input_file,
                        "--output", output_dir,
                        "--threads", str(download_threads)
                    ]
                    
                    output_container = st.empty()
                    success, output = run_script_with_output(cmd, output_container)
                    
                    if success:
                        st.success(f"✅ Downloads completed!")
                        st.info("Ready for Step 4: Create YouTube Playlist")
                        
                        # Count downloaded files
                        try:
                            downloaded_files = list(Path(output_dir).glob("*.mp3"))
                            st.metric("Downloaded Files", len(downloaded_files))
                        except:
                            pass
                    else:
                        st.error("❌ Download failed")
                        with st.expander("View output"):
                            st.text(output)
            else:
                st.error("Please provide a valid input file")

def create_playlist_page():
    st.header("📋 Create YouTube Playlist")
    st.write("Create a YouTube Music playlist from your tracks")
    
    col1, col2 = st.columns(2)
    
    with col1:
        input_file = st.text_input(
            "Enriched JSON file:",
            value="out/enriched_output.json",
            help="Same file from Step 2"
        )
        
        if input_file and os.path.exists(input_file):
            try:
                with open(input_file, 'r') as f:
                    data = json.load(f)
                valid_videos = [t for t in data if t.get('youtube', {}).get('id', {}).get('videoId')]
                st.success(f"✅ Found {len(valid_videos)} videos for playlist")
            except:
                st.error("Invalid JSON file")
        elif input_file:
            st.warning("File not found")
    
    with col2:
        st.subheader("Playlist Settings")
        
        playlist_title = st.text_input(
            "Playlist title:",
            placeholder="My Spotify Playlist"
        )
        
        privacy = st.selectbox(
            "Privacy setting:",
            options=["private", "unlisted", "public"],
            index=0
        )
        
        if st.button("Create YouTube Playlist", type="primary"):
            if input_file and os.path.exists(input_file) and playlist_title:
                with st.spinner("Creating playlist..."):
                    cmd = [
                        ".venv/bin/python", "yt_PushMK1.py",
                        "--input", input_file,
                        "--title", playlist_title,
                        "--privacy", privacy
                    ]
                    
                    output_container = st.empty()
                    success, output = run_script_with_output(cmd, output_container)
                    
                    if success:
                        st.success(f"✅ Created playlist: {playlist_title}")
                        st.balloons()
                        
                        # Try to extract playlist URL from output
                        for line in output.split('\n'):
                            if 'youtube.com/playlist' in line:
                                st.markdown(f"**Playlist URL:** {line.strip()}")
                                break
                    else:
                        st.error("❌ Playlist creation failed")
                        with st.expander("View output"):
                            st.text(output)
            else:
                st.error("Please provide both a valid file and playlist title")

    # Show pipeline summary
    st.markdown("---")
    st.subheader("📊 Pipeline Status")
    
    summary_cols = st.columns(4)
    
    # Check each step
    with summary_cols[0]:
        spotify_file = "out/playlist.json"
        if os.path.exists(spotify_file):
            try:
                with open(spotify_file, 'r') as f:
                    data = json.load(f)
                st.metric("Spotify Export", f"{len(data)} tracks", "✅ Complete")
            except:
                st.metric("Spotify Export", "Error", "❌ Invalid")
        else:
            st.metric("Spotify Export", "Not done", "⏳ Pending")
    
    with summary_cols[1]:
        enriched_file = "out/enriched_output.json"
        if os.path.exists(enriched_file):
            try:
                with open(enriched_file, 'r') as f:
                    data = json.load(f)
                found = sum(1 for t in data if t.get('youtube'))
                rate = (found / len(data)) * 100
                st.metric("YouTube Search", f"{rate:.0f}% found", "✅ Complete")
            except:
                st.metric("YouTube Search", "Error", "❌ Invalid")
        else:
            st.metric("YouTube Search", "Not done", "⏳ Pending")
    
    with summary_cols[2]:
        download_dir = "downloads/"
        if os.path.exists(download_dir):
            try:
                downloaded = list(Path(download_dir).glob("*.mp3"))
                st.metric("Downloads", f"{len(downloaded)} files", "✅ Complete")
            except:
                st.metric("Downloads", "Error", "❌ Invalid")
        else:
            st.metric("Downloads", "Not done", "⏳ Pending")
    
    with summary_cols[3]:
        st.metric("Playlist", "Manual check", "🔗 Check YouTube")

if __name__ == "__main__":
    main()
