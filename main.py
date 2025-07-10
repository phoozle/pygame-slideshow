import pygame
import os
import time
import qrcode
import imageio  # For video playback
import logging
import yaml  # For loading config
import random  # For random transitions
import socket
import platform
import subprocess
from PIL import Image
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import numpy as np  # For imageio frame arrays and pygame surfarray

# Set environment variables for better Raspberry Pi compatibility
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
os.environ['SDL_AUDIODRIVER'] = 'alsa'

# Don't force a specific video driver - let pygame auto-detect
# This allows proper fallback from fbcon to x11

# Load config from YAML
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'config.yaml')
try:
    with open(CONFIG_FILE, 'r') as f:
        config = yaml.safe_load(f)
except Exception as e:
    logging.error(f"Error loading config.yaml: {str(e)}")
    config = {}  # Fallback to defaults if needed

# Config values (with defaults if not in YAML)
SLIDE_DIR = os.path.join(SCRIPT_DIR, config.get('slide_dir', 'slides'))
ERROR_LOG = os.path.join(SCRIPT_DIR, config.get('error_log', 'errors.txt'))
SLIDE_DURATION = config.get('slide_duration', 10)
TRANSITION_DURATION = config.get('transition_duration', 1.0)
FPS = config.get('fps', 30)
FONT_SIZE = config.get('font_size', 24)
TEXT_COLOR = tuple(config.get('text_color', [255, 255, 255]))
FOOTER_BG_COLOR = tuple(config.get('footer_bg_color', [0, 0, 255, 128]))
ERROR_RETRY_DELAY = config.get('error_retry_delay', 30)
QR_BOX_SIZE = config.get('qr_box_size', 5)
QR_BORDER = config.get('qr_border', 2)
AVAILABLE_TRANSITIONS = config.get('available_transitions', ['fade', 'slide', 'dissolve', 'zoom'])
TRANSITION_FPS = config.get('transition_fps', 15)  # Lower FPS for transitions on Pi
USE_FAST_TRANSITIONS = config.get('use_fast_transitions', False)  # Simplified transitions for Pi

# Setup logging to errors.txt (only errors)
logging.basicConfig(filename=ERROR_LOG, level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

pygame.init()

# Try different video drivers and display modes
screen = None
drivers_to_try = [
    (None, "auto-detect"),  # Let pygame choose
    ("x11", "X11"),
    ("fbcon", "framebuffer console"),
    ("dummy", "dummy (headless)")
]

display_modes = [
    (pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF, "hardware accelerated fullscreen"),
    (pygame.FULLSCREEN | pygame.SWSURFACE | pygame.DOUBLEBUF, "software fullscreen"),
    (pygame.FULLSCREEN, "basic fullscreen"),
    (0, "windowed mode")
]

for driver, driver_name in drivers_to_try:
    if driver:
        os.environ['SDL_VIDEODRIVER'] = driver
    elif 'SDL_VIDEODRIVER' in os.environ:
        del os.environ['SDL_VIDEODRIVER']

    try:
        pygame.display.quit()
        pygame.display.init()

        for mode, mode_name in display_modes:
            try:
                if mode == 0:
                    screen = pygame.display.set_mode((1280, 720), mode)
                else:
                    screen = pygame.display.set_mode((0, 0), mode)
                print(f"Display initialized: {driver_name} with {mode_name}")
                break
            except pygame.error as e:
                continue

        if screen:
            break

    except pygame.error as e:
        continue

if screen is None:
    print("ERROR: Could not initialize any display mode")
    pygame.quit()
    exit(1)
font = pygame.font.SysFont('freesans', FONT_SIZE)
startup_font = pygame.font.SysFont('freesans', 20)  # Smaller font for startup info
clock = pygame.time.Clock()  # For timing control

def get_system_info():
    """Get system information including IP addresses."""
    info = []

    # Basic system info
    info.append(f"System: {platform.system()} {platform.release()}")
    info.append(f"Machine: {platform.machine()}")
    info.append(f"Hostname: {socket.gethostname()}")
    info.append("")

    # Get IP addresses
    try:
        # Get all network interfaces
        if platform.system() == "Darwin":  # macOS
            result = subprocess.run(['ifconfig'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            current_interface = None
            for line in lines:
                if line and not line.startswith('\t') and not line.startswith(' '):
                    current_interface = line.split(':')[0]
                elif 'inet ' in line and '127.0.0.1' not in line:
                    ip = line.split('inet ')[1].split(' ')[0]
                    info.append(f"{current_interface}: {ip}")
        else:  # Linux/Raspbian
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            if result.returncode == 0:
                ips = result.stdout.strip().split()
                for i, ip in enumerate(ips):
                    info.append(f"IP {i+1}: {ip}")

            # Also try ip command for interface names
            try:
                result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True)
                lines = result.stdout.split('\n')
                current_interface = None
                for line in lines:
                    if line and not line.startswith(' '):
                        if ':' in line:
                            current_interface = line.split(':')[1].strip().split('@')[0]
                    elif 'inet ' in line and '127.0.0.1' not in line and '/32' not in line:
                        ip = line.strip().split('inet ')[1].split('/')[0]
                        if current_interface:
                            info.append(f"{current_interface}: {ip}")
            except:
                pass
    except Exception as e:
        info.append(f"Error getting IP addresses: {str(e)}")

    return info

def display_startup_message():
    """Display startup message with system information for 60 seconds."""
    system_info = get_system_info()

    start_time = time.time()
    while time.time() - start_time < 60:
        # Check for quit events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                elif event.key == pygame.K_q and pygame.key.get_mods() & pygame.KMOD_GUI:
                    return False
                elif event.key == pygame.K_SPACE:  # Allow space to skip startup
                    return True

        # Draw startup screen
        screen.fill((0, 0, 0))  # Black background

        # Title
        title_surf = font.render("PyGame Slideshow - Starting Up", True, (255, 255, 255))
        title_rect = title_surf.get_rect(center=(screen.get_width() // 2, 50))
        screen.blit(title_surf, title_rect)

        # System info
        y_pos = 120
        for line in system_info:
            if line.strip():  # Skip empty lines for spacing
                text_surf = startup_font.render(line, True, (200, 200, 200))
                screen.blit(text_surf, (50, y_pos))
            y_pos += 30

        # Time remaining
        remaining = int(60 - (time.time() - start_time))
        time_surf = startup_font.render(f"Starting slideshow in {remaining} seconds... (Press SPACE to skip)", True, (255, 255, 0))
        screen.blit(time_surf, (50, screen.get_height() - 50))

        pygame.display.flip()
        clock.tick(FPS)

    return True

def display_error(message):
    """Display error message on screen for a duration."""
    screen.fill((0, 0, 0))  # Black background
    text_surf = font.render(message, True, (255, 0, 0))  # Red text
    text_rect = text_surf.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2))
    screen.blit(text_surf, text_rect)
    pygame.display.flip()
    time.sleep(ERROR_RETRY_DELAY)

def load_content():
    global slides, footer_lines, qr_surface
    slides = []
    screen_size = screen.get_size()
    for file in sorted(os.listdir(SLIDE_DIR)):  # Alphabetical order
        try:
            if file.lower().endswith(('.jpg', '.png')):
                img_path = os.path.join(SLIDE_DIR, file)
                img = pygame.image.load(img_path)
                img = pygame.transform.scale(img, screen_size)
                # Convert to screen format for faster blitting
                img = img.convert()
                slides.append({'type': 'image', 'surface': img})
            elif file.lower().endswith('.mp4'):
                video_path = os.path.join(SLIDE_DIR, file)
                # Validate video file can be opened
                reader = imageio.get_reader(video_path)
                reader.close()  # Close immediately after validation
                slides.append({'type': 'video', 'path': video_path})
        except Exception as e:
            logging.error(f"Error loading slide '{file}': {str(e)}")
            # Continue to next file, skip invalid

    # Load footer text
    footer_lines = []
    footer_path = os.path.join(SLIDE_DIR, 'footer.txt')
    if os.path.exists(footer_path):
        try:
            with open(footer_path, 'r') as f:
                footer_text = f.read().strip()
                footer_lines = [line for line in footer_text.split('\n') if line.strip()]
        except Exception as e:
            logging.error(f"Error reading footer.txt: {str(e)}")

    # Load and generate QR code
    qr_surface = None
    qr_path = os.path.join(SLIDE_DIR, 'qr_url.txt')
    if os.path.exists(qr_path):
        try:
            with open(qr_path, 'r') as f:
                url = f.read().strip()
            if url:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=QR_BOX_SIZE,
                    border=QR_BORDER,
                )
                qr.add_data(url)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                img = img.convert('RGB')
                qr_surface = pygame.image.fromstring(img.tobytes(), img.size, img.mode)
                # Convert QR surface for faster blitting
                qr_surface = qr_surface.convert_alpha()
        except Exception as e:
            logging.error(f"Error generating QR code: {str(e)}")

def render_overlays():
    # Render footer with blue background if lines exist
    if footer_lines:
        line_height = FONT_SIZE + 5
        footer_height = len(footer_lines) * line_height
        # Calculate width: max text width + padding
        max_width = max(font.size(line)[0] for line in footer_lines) + 40  # 20px padding each side
        y = screen.get_height() - footer_height - 20  # Padding from bottom

        # Create semi-transparent blue background surface
        bg_surf = pygame.Surface((max_width, footer_height + 10), pygame.SRCALPHA)  # +10 for inner padding
        bg_surf = bg_surf.convert_alpha()  # Convert for faster blitting
        bg_surf.fill(FOOTER_BG_COLOR)

        # Blit background
        screen.blit(bg_surf, (10, y))  # 10px left padding

        # Render text lines on top
        text_y = y + 5  # Inner top padding
        for line in footer_lines:
            text_surf = font.render(line, True, TEXT_COLOR)
            screen.blit(text_surf, (20, text_y))  # Adjusted for padding
            text_y += line_height

    # Render QR code in bottom-right if available (no background for QR)
    if qr_surface:
        qr_width, qr_height = qr_surface.get_size()
        x = screen.get_width() - qr_width - 20
        y = screen.get_height() - qr_height - 20
        screen.blit(qr_surface, (x, y))

# Optimized transition functions for Raspberry Pi performance
def transition_fade(current_surf, next_surf):
    if USE_FAST_TRANSITIONS:
        # Fast fade: just 3 steps
        transition_steps = 3
        alphas = [200, 128, 64]
    else:
        transition_steps = int(TRANSITION_DURATION * TRANSITION_FPS)
        alphas = [int(255 * (1 - step / transition_steps)) for step in range(transition_steps)]

    for alpha in alphas:
        screen.blit(next_surf, (0, 0))
        temp_surf = current_surf.copy()
        temp_surf = temp_surf.convert_alpha()  # Convert for alpha blending
        temp_surf.set_alpha(alpha)
        screen.blit(temp_surf, (0, 0))
        render_overlays()
        pygame.display.flip()
        clock.tick(TRANSITION_FPS)

def transition_slide(current_surf, next_surf):
    width = screen.get_width()
    if USE_FAST_TRANSITIONS:
        # Fast slide: just 4 steps
        positions = [0.25, 0.5, 0.75, 1.0]
    else:
        transition_steps = int(TRANSITION_DURATION * TRANSITION_FPS)
        positions = [step / transition_steps for step in range(transition_steps)]

    for progress in positions:
        screen.blit(current_surf, (-width * progress, 0))
        screen.blit(next_surf, (width * (1 - progress), 0))
        render_overlays()
        pygame.display.flip()
        clock.tick(TRANSITION_FPS)

def transition_dissolve(current_surf, next_surf):
    # Optimized dissolve using rectangular blocks instead of individual pixels
    block_size = 8 if USE_FAST_TRANSITIONS else 4
    width, height = screen.get_size()
    blocks_x = width // block_size
    blocks_y = height // block_size

    # Create list of block positions
    blocks = [(x * block_size, y * block_size) for x in range(blocks_x) for y in range(blocks_y)]
    random.shuffle(blocks)

    if USE_FAST_TRANSITIONS:
        # Fast dissolve: fewer steps
        transition_steps = 8
    else:
        transition_steps = int(TRANSITION_DURATION * TRANSITION_FPS)

    # Start with current surface
    work_surf = current_surf.copy()
    blocks_per_step = len(blocks) // transition_steps

    for step in range(transition_steps):
        start_idx = step * blocks_per_step
        end_idx = start_idx + blocks_per_step if step < transition_steps - 1 else len(blocks)

        # Copy blocks from next surface to work surface
        for i in range(start_idx, end_idx):
            x, y = blocks[i]
            block_rect = pygame.Rect(x, y, block_size, block_size)
            work_surf.blit(next_surf, (x, y), block_rect)

        screen.blit(work_surf, (0, 0))
        render_overlays()
        pygame.display.flip()
        clock.tick(TRANSITION_FPS)

def transition_zoom(current_surf, next_surf):
    center_x, center_y = screen.get_width() // 2, screen.get_height() // 2

    if USE_FAST_TRANSITIONS:
        # Pre-compute just 4 zoom levels
        scales = [0.75, 0.5, 0.25, 0.0]
    else:
        transition_steps = int(TRANSITION_DURATION * TRANSITION_FPS)
        scales = [1 - (step / transition_steps) for step in range(transition_steps)]

    # Pre-scale the surfaces to avoid repeated smoothscale calls
    scaled_surfaces = []
    for scale in scales:
        if scale > 0:
            current_scale = scale
            next_scale = 1 - scale

            # Use regular scale instead of smoothscale for better performance
            scaled_current = pygame.transform.scale(current_surf,
                (max(1, int(screen.get_width() * current_scale)),
                 max(1, int(screen.get_height() * current_scale))))
            scaled_next = pygame.transform.scale(next_surf,
                (max(1, int(screen.get_width() * next_scale)),
                 max(1, int(screen.get_height() * next_scale))))

            scaled_surfaces.append((scaled_current, scaled_next))

    for scaled_current, scaled_next in scaled_surfaces:
        current_rect = scaled_current.get_rect(center=(center_x, center_y))
        next_rect = scaled_next.get_rect(center=(center_x, center_y))

        screen.fill((0, 0, 0))
        screen.blit(scaled_current, current_rect)
        screen.blit(scaled_next, next_rect)
        render_overlays()
        pygame.display.flip()
        clock.tick(TRANSITION_FPS)

# Map for random selection
TRANSITION_MAP = {
    'fade': transition_fade,
    'slide': transition_slide,
    'dissolve': transition_dissolve,
    'zoom': transition_zoom
}

# Fast transitions for Pi - only use the most efficient ones
FAST_TRANSITIONS = ['slide', 'fade'] if USE_FAST_TRANSITIONS else AVAILABLE_TRANSITIONS

class ReloadHandler(FileSystemEventHandler):
    def on_modified(self, event):
        load_content()  # Reload everything on change

# Start filesystem watcher
observer = Observer()
observer.schedule(ReloadHandler(), SLIDE_DIR, recursive=False)
observer.start()

slides = []
footer_lines = []
qr_surface = None
load_content()
current_slide = 0

# Show startup message first
running = display_startup_message()
if not running:
    observer.stop()
    observer.join()
    pygame.quit()
    exit()
while running:
    try:
        if slides:
            slide = slides[current_slide]

            if slide['type'] == 'image':
                # Display image fully
                screen.blit(slide['surface'], (0, 0))
                render_overlays()
                pygame.display.flip()

                # Non-blocking hold for duration
                start_time = time.time()
                while time.time() - start_time < SLIDE_DURATION and running:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            running = False
                        elif event.type == pygame.KEYDOWN:
                            if event.key == pygame.K_ESCAPE:
                                running = False
                            elif event.key == pygame.K_q and pygame.key.get_mods() & pygame.KMOD_GUI:
                                running = False
                    clock.tick(FPS)

                if not running:
                    break

                # Random transition to next if it's an image
                next_index = (current_slide + 1) % len(slides)
                next_slide = slides[next_index]
                if next_slide['type'] == 'image':
                    available_transitions = FAST_TRANSITIONS if USE_FAST_TRANSITIONS else AVAILABLE_TRANSITIONS
                    trans_type = random.choice(available_transitions)
                    TRANSITION_MAP[trans_type](slide['surface'], next_slide['surface'])
                    # Check events during transition (added to each func, but for brevity omitted here; add if needed)

            elif slide['type'] == 'video':
                # Play video
                reader = imageio.get_reader(slide['path'])
                for frame in reader:
                    if not running:
                        break

                    # Frame is numpy array (h, w, c) RGB
                    frame_surf = pygame.surfarray.make_surface(np.swapaxes(frame, 0, 1))  # Swap to (w, h, c) for surfarray
                    frame_surf = pygame.transform.scale(frame_surf, screen.get_size())
                    frame_surf = frame_surf.convert()  # Convert for faster blitting

                    screen.blit(frame_surf, (0, 0))
                    render_overlays()
                    pygame.display.flip()

                    # Check events
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            running = False
                        elif event.type == pygame.KEYDOWN:
                            if event.key == pygame.K_ESCAPE:
                                running = False
                            elif event.key == pygame.K_q and pygame.key.get_mods() & pygame.KMOD_GUI:
                                running = False

                    clock.tick(FPS)  # Cap to FPS (adjust if video FPS differs)

                reader.close()

            current_slide = (current_slide + 1) % len(slides)
        else:
            display_error("No valid slides found. Retrying...")
            load_content()
    except Exception as e:
        logging.error(f"Runtime error: {str(e)}")
        display_error("Invalid configuration. Retrying...")
        load_content()  # Retry loading after display

observer.stop()
observer.join()
pygame.quit()
