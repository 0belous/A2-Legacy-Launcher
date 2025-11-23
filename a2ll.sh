#!/bin/bash
export PATH="$PATH:$HOME/.local/bin"

install_dependencies() {
    DEBIAN_FRONTEND=noninteractive apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y -o Dpkg::Options::="--force-confold" android-tools python git unzip aapt apksigner jq termux-api dialog
    python -m pip install pipx
    python -m pipx install a2_legacy_launcher
    python -m pipx ensurepath
    export PATH="$PATH:$HOME/.local/bin"
}

OUTPUT=$(a2ll -ls 2>&1)
LINE_COUNT=$(echo "$OUTPUT" | wc -l)

if [ $? -ne 0 ] || [ "$LINE_COUNT" -lt 10 ]; then
    install_dependencies
    OUTPUT=$(a2ll -ls 2>&1)
fi

CONFIG_FILE="$HOME/.config/a2-legacy-launcher/config.yml"
if [ -f "$CONFIG_FILE" ]; then
    sed -i 's/autoupdate: [tT]rue/autoupdate: false/' "$CONFIG_FILE"
fi

if ! command -v dialog &> /dev/null; then
    apt-get install -y dialog
fi

VERSIONS=$(echo "$OUTPUT" | grep "Version:" | awk '{print $3}')

if [ -z "$VERSIONS" ]; then
    echo "Error: Could not find any versions in a2ll output."
    exit 1
fi

OPTIONS=()
for VER in $VERSIONS; do
    OPTIONS+=("$VER" "" "off")
done

SELECTION_STR=$(dialog --stdout --checklist "Select Versions to Install" 0 0 0 "${OPTIONS[@]}")

if [ -z "$SELECTION_STR" ]; then
    echo "Selection cancelled."
    exit 0
fi

SELECTED_VERSIONS=$(echo "$SELECTION_STR" | tr -d '"')

if [ -z "$SELECTED_VERSIONS" ]; then
    echo "No versions selected."
    exit 0
fi

for VER in $SELECTED_VERSIONS; do
    a2ll "$VER"
done