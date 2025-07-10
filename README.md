# Raspberry Pi Slideshow

A simple, efficient slideshow application to display images and videos. Supports editable content, footer text, QR codes, transitions, and error handling.

## Requirements
- Python 3.11+
- Dependencies (listed in `requirements.txt`):
  - pygame==2.5.2
  - watchdog==3.0.0
  - qrcode==8.2
  - pillow==11.3.0
  - opencv-python==4.10.0.84
  - pyyaml==6.0.2

## Installation
1. Clone the repository:
   ```
   git clone https://github.com/phoozle/pygame-slideshow.git
   cd pygame-slideshow
   ```
2. Install system packages (for OpenCV and others):
   ```
   sudo apt update
   sudo apt install python3-pip python3-opencv python3-pil
   ```
3. Install Python dependencies:
   ```
   pip3 install -r requirements.txt
   ```

## Usage
1. Place content in `slides/`:
   - Images: .jpg/.png (e.g., `01_slide.jpg`)
   - Videos: .mp4 (e.g., `02_video.mp4`)
   - Footer: `footer.txt` (plain text lines)
   - QR: `qr_url.txt` (single URL)
2. Configure settings in `config.yaml` (e.g., durations, colors).
3. Run the slideshow:
   ```
   python3 main.py
   ```
   - Runs fullscreen; quit with Esc.
   - Auto-reloads on file changes.
   - Errors log to `errors.txt`; displays message and retries.

## Development
- Edit `main.py` for core logic (e.g., add transitions via `TRANSITION_MAP`).
- Modify `config.yaml` for tunable params without code changes.
- Contribute: Fork, PR with improvements (e.g., new features, bug fixes).

For issues, check `errors.txt`.