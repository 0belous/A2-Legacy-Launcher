#!/bin/bash

TMP_MSG="/tmp/a2ll_migration_$RANDOM.sh"
cat << 'EOF' > "$TMP_MSG"
#!/bin/bash
echo "You are running legacy launcher 1.3 which is installed and managed via pipx and pypi."
echo "This system is now deprecated, to update to the latest version please check https://github.com/0belous/UE-Legacy-Launcher."
echo "To keep using an old version and stop seeing this message disable autoupdate in your config.yml"
echo ""
read -p "Press [Enter] to exit..."
rm -f "$0"
EOF
chmod +x "$TMP_MSG"

if [ "$(uname)" == "Darwin" ]; then
    osascript -e "tell application \"Terminal\" to do script \"$TMP_MSG\""
else
    if command -v x-terminal-emulator >/dev/null; then
        x-terminal-emulator -e "$TMP_MSG"
    elif command -v gnome-terminal >/dev/null; then
        gnome-terminal -- "$TMP_MSG"
    elif command -v konsole >/dev/null; then
        konsole -e "$TMP_MSG"
    elif command -v xterm >/dev/null; then
        xterm -e "$TMP_MSG"
    else
        "$TMP_MSG"
    fi
fi