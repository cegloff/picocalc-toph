#!/bin/sh
# Generate apps.json manifest from app directories
set -e

APPS_DIR="/usr/share/nginx/html/apps"
OUT="/usr/share/nginx/html/apps.json"

printf '{"apps":[' > "$OUT"
first=true

for app_json in "$APPS_DIR"/*/app.json; do
    [ -f "$app_json" ] || continue
    app_dir=$(dirname "$app_json")
    slug=$(basename "$app_dir")

    # Read name from app.json
    name=$(sed -n 's/.*"name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$app_json")

    # List .py files
    files=""
    for f in "$app_dir"/*.py; do
        [ -f "$f" ] || continue
        fname=$(basename "$f")
        [ -n "$files" ] && files="$files,"
        files="$files\"$fname\""
    done

    # Include icon.raw if present
    if [ -f "$app_dir/icon.raw" ]; then
        [ -n "$files" ] && files="$files,"
        files="$files\"icon.raw\""
    fi

    # Total size in bytes
    size=$(du -sb "$app_dir" | cut -f1)

    if [ "$first" = true ]; then
        first=false
    else
        printf ',' >> "$OUT"
    fi

    printf '{"slug":"%s","name":"%s","files":[%s],"size":%s}' \
        "$slug" "$name" "$files" "$size" >> "$OUT"
done

printf ']}' >> "$OUT"
echo "Generated $OUT"
