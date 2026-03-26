#!/bin/bash

# ──────────────────────────────────────────────────────────────
# GlitchLab Installer
# ──────────────────────────────────────────────────────────────

# Ask for consent
zenity --question --title="Install GlitchLab" \
       --text="This will install GlitchLab system-wide for all users.\nDo you want to continue?" \
       --width=400

if [ $? -ne 0 ]; then
    echo "Installation canceled."
    exit 1
fi

# Ask for location of GlitchLab.py
GLITCH_PATH=$(zenity --file-selection --title="Select GlitchLab.py")
if [ -z "$GLITCH_PATH" ]; then
    zenity --error --text="No file selected. Exiting."
    exit 1
fi

# Destination for script
DEST_BIN="/usr/local/bin/GlitchLab.py"

# Copy script and make executable
sudo cp "$GLITCH_PATH" "$DEST_BIN"
sudo chmod +x "$DEST_BIN"

# Create desktop file
DESKTOP_FILE="/usr/share/applications/GlitchLab.desktop"
sudo tee "$DESKTOP_FILE" > /dev/null <<EOF
[Desktop Entry]
Type=Application
Name=GlitchLab
Comment=Glitch audio/video files
Exec=python3 $DEST_BIN
Icon=GlitchLabs.png
Terminal=false
Categories=Utility;AudioVideo;
EOF

zenity --info --title="Installation Complete" --text="GlitchLab has been installed successfully!"
