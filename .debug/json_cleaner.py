import json
import os

def main():
    input_path = input("Enter path to enriched JSON file: ").strip()
    output_path = input("Enter path for output TXT file: ").strip()

    if not os.path.isfile(input_path):
        print(" Input file not found.")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    links = []
    for entry in data:
        youtube = entry.get("youtube")
        if youtube and youtube.get("id") and youtube["id"].get("videoId"):
            video_id = youtube["id"]["videoId"]
            links.append(f"https://www.youtube.com/watch?v={video_id}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(links))

    print(f"\n Extracted {len(links)} links.")
    print(f" Saved to: {output_path}")

if __name__ == "__main__":
    main()
