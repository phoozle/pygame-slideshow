import pygame
import os
import time
import qrcode
import cv2  # For video playback
import logging
import yaml  # For loading config
import random  # For random transitions
from PIL import Image
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

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

# Setup logging to errors.txt (only errors)
logging.basicConfig(filename=ERROR_LOG, level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

pygame.init()
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
font = pygame.font.SysFont('freesans', FONT_SIZE)
clock = pygame.time.Clock()  # For timing control

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
                slides.append({'type': 'image', 'surface': img})
            elif file.lower().endswith('.mp4'):
                video_path = os.path.join(SLIDE_DIR, file)
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    raise ValueError(f"Invalid video format: {file}")
                cap.release()
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

# Transition functions
def transition_fade(current_surf, next_surf):
    transition_steps = int(TRANSITION_DURATION * FPS)
    for step in range(transition_steps):
        alpha = int(255 * (1 - step / transition_steps))
        screen.blit(next_surf, (0, 0))
        temp_surf = current_surf.copy()
        temp_surf.set_alpha(alpha)
        screen.blit(temp_surf, (0, 0))
        render_overlays()
        pygame.display.flip()
        clock.tick(FPS)

def transition_slide(current_surf, next_surf):
    width = screen.get_width()
    transition_steps = int(TRANSITION_DURATION * FPS)
    for step in range(transition_steps):
        progress = step / transition_steps
        screen.blit(current_surf, (-width * progress, 0))
        screen.blit(next_surf, (width * (1 - progress), 0))
        render_overlays()
        pygame.display.flip()
        clock.tick(FPS)

def transition_dissolve(current_surf, next_surf):
    px_current = pygame.PixelArray(current_surf.copy())
    px_next = pygame.PixelArray(next_surf)
    pixels = list(range(screen.get_width() * screen.get_height()))
    random.shuffle(pixels)
    transition_steps = int(TRANSITION_DURATION * FPS)
    chunk_size = len(pixels) // transition_steps
    for step in range(transition_steps):
        start = step * chunk_size
        end = start + chunk_size if step < transition_steps - 1 else len(pixels)
        for i in range(start, end):
            x = pixels[i] % screen.get_width()
            y = pixels[i] // screen.get_width()
            px_current[x, y] = px_next[x, y]
        temp_surf = px_current.make_surface()
        screen.blit(temp_surf, (0, 0))
        render_overlays()
        pygame.display.flip()
        clock.tick(FPS)

def transition_zoom(current_surf, next_surf):
    center_x, center_y = screen.get_width() // 2, screen.get_height() // 2
    transition_steps = int(TRANSITION_DURATION * FPS)
    for step in range(transition_steps):
        progress = step / transition_steps
        # Zoom out current
        current_scale = 1 - progress
        scaled_current = pygame.transform.smoothscale(current_surf, (int(screen.get_width() * current_scale), int(screen.get_height() * current_scale)))
        current_rect = scaled_current.get_rect(center=(center_x, center_y))
        # Zoom in next
        next_scale = progress
        scaled_next = pygame.transform.smoothscale(next_surf, (int(screen.get_width() * next_scale), int(screen.get_height() * next_scale)))
        next_rect = scaled_next.get_rect(center=(center_x, center_y))
        screen.fill((0, 0, 0))  # Black bg during zoom
        screen.blit(scaled_current, current_rect)
        screen.blit(scaled_next, next_rect)
        render_overlays()
        pygame.display.flip()
        clock.tick(FPS)

# Map for random selection
TRANSITION_MAP = {
    'fade': transition_fade,
    'slide': transition_slide,
    'dissolve': transition_dissolve,
    'zoom': transition_zoom
}

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

running = True
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
                    trans_type = random.choice(AVAILABLE_TRANSITIONS)
                    TRANSITION_MAP[trans_type](slide['surface'], next_slide['surface'])
                    # Check events during transition (added to each func, but for brevity omitted here; add if needed)

            elif slide['type'] == 'video':
                # Play video
                cap = cv2.VideoCapture(slide['path'])
                if not cap.isOpened():
                    raise ValueError(f"Failed to open video: {slide['path']}")
                while cap.isOpened() and running:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    # Convert BGR to RGB and to Pygame surface
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_surf = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
                    frame_surf = pygame.transform.scale(frame_surf, screen.get_size())

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

                cap.release()

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
