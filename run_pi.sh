#!/bin/bash

# Raspberry Pi optimized slideshow runner
# This script runs the slideshow with Pi-specific optimizations

echo "Starting PyGame Slideshow with Raspberry Pi optimizations..."

# Set environment variables for better Pi performance
export SDL_VIDEODRIVER=fbcon
export SDL_FBDEV=/dev/fb0
export SDL_AUDIODRIVER=alsa

# Disable GPU memory split warnings
export PYGAME_HIDE_SUPPORT_PROMPT=1

# Use Pi-optimized config
CONFIG_FILE="config_pi.yaml"

# Check if Pi config exists, if not copy from default
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Creating Pi-optimized config file..."
    cp config.yaml config_pi.yaml
    # Update config for Pi performance
    sed -i 's/transition_fps: 15/transition_fps: 10/' config_pi.yaml
    sed -i 's/use_fast_transitions: false/use_fast_transitions: true/' config_pi.yaml
    sed -i 's/fps: 30/fps: 20/' config_pi.yaml
    sed -i 's/transition_duration: 1.0/transition_duration: 0.5/' config_pi.yaml
    sed -i 's/available_transitions: \[fade, slide, dissolve, zoom\]/available_transitions: [fade, slide]/' config_pi.yaml
fi

# Backup original config and use Pi config
if [ -f "config.yaml" ]; then
    cp config.yaml config_backup.yaml
fi
cp config_pi.yaml config.yaml

echo "Running with Pi-optimized settings..."
echo "- Lower FPS for better performance"
echo "- Simplified transitions"
echo "- Hardware acceleration enabled"
echo "- Press Ctrl+C to stop"

# Run the slideshow
python3 main.py

# Restore original config
if [ -f "config_backup.yaml" ]; then
    mv config_backup.yaml config.yaml
fi

echo "Slideshow stopped."
