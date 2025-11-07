"""
Download script for Qwen-VL GGUF model and mmproj files
Run this once to download the model files to the models/ directory
"""

import os
import urllib.request
from pathlib import Path

MODEL_DIR = Path(__file__).parent.parent / "models"
MODEL_DIR.mkdir(exist_ok=True)

# HuggingFace model files
BASE_URL = "https://huggingface.co/huihui-ai/Huihui-Qwen3-VL-2B-Instruct-abliterated/resolve/main/GGUF/"

FILES_TO_DOWNLOAD = {
    # Main model - Q4_K_M recommended for balance of quality/performance
    "model": "huihui-qwen3-vl-2b-instruct-abliterated-q4_k_m.gguf",
    # Vision projection for image processing
    "mmproj": "mmproj-huihui-qwen3-vl-2b-instruct-abliterated-f16.gguf"
}


def download_file(url: str, dest: Path):
    """Download file with progress bar"""
    if dest.exists():
        print(f"✓ {dest.name} already exists, skipping...")
        return

    print(f"Downloading {dest.name}...")
    print(f"From: {url}")

    def progress_hook(count, block_size, total_size):
        percent = min(int(count * block_size * 100 / total_size), 100)
        print(f"\r  Progress: {percent}%", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, dest, progress_hook)
        print(f"\n✓ Downloaded {dest.name}")
    except Exception as e:
        print(f"\n✗ Error downloading {dest.name}: {e}")
        if dest.exists():
            dest.unlink()


def main():
    print("=" * 60)
    print("DiaryML Model Downloader")
    print("=" * 60)
    print(f"\nDownloading to: {MODEL_DIR.absolute()}\n")

    for file_type, filename in FILES_TO_DOWNLOAD.items():
        url = BASE_URL + filename
        dest = MODEL_DIR / filename
        download_file(url, dest)

    print("\n" + "=" * 60)
    print("Download complete!")
    print("=" * 60)
    print("\nModel files:")
    for file in MODEL_DIR.glob("*.gguf"):
        size_mb = file.stat().st_size / (1024 * 1024)
        print(f"  • {file.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
