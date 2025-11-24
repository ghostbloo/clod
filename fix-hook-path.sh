#!/bin/bash
# Helper script to fix the auto_format hook path

echo "Fixing auto_format hook paths..."

# Function to fix hook path in a settings file
fix_settings_file() {
    local file="$1"
    if [ -f "$file" ]; then
        echo "Checking $file..."
        if grep -q "/Users/me/code/ai/clod/.claude/hooks/auto_format.py" "$file"; then
            echo "  Found old absolute path in $file"
            # Create backup
            cp "$file" "$file.backup"
            # Replace the absolute path with relative path
            sed -i.tmp 's|python /Users/me/code/ai/clod/.claude/hooks/auto_format.py|python .claude/hooks/auto_format.py|g' "$file"
            rm -f "$file.tmp"
            echo "  ✓ Fixed! Backup saved to $file.backup"
        else
            echo "  ✓ Already correct or not found"
        fi
    else
        echo "  File doesn't exist: $file"
    fi
}

# Fix user-level settings
fix_settings_file "$HOME/.claude/settings.json"

# Fix project-level settings (current directory)
fix_settings_file "./.claude/settings.json"

# Fix local settings
fix_settings_file "./.claude/settings.local.json"

echo ""
echo "Done! Please restart your Claude Code session for changes to take effect."
echo ""
echo "If the issue persists, check these files manually:"
echo "  - $HOME/.claude/settings.json"
echo "  - ./.claude/settings.json"
echo "  - ./.claude/settings.local.json"
