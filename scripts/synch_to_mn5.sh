#!/bin/bash

# --- Configuration ---
REMOTE_USER=bsc018186
REMOTE_HOST=transfer1.bsc.es
REMOTE_DIR=/gpfs/scratch/bsc18/bsc018186/
LOCAL_DIR=/home/bscuser/synched_mnt/VMem

# Folders/files to exclude from syncing
EXCLUDES=(
		".csconfig/"
    "data/"
    "dump/"
    "stats/"
    "bin/"
    "figures/"
    "figures_PUBLISHED/"
		"traces/"
		"__pycache__"
)

# Build rsync exclude parameters
EXCLUDE_PARAMS=()
for i in "${EXCLUDES[@]}"; do
    EXCLUDE_PARAMS+=("--exclude=$i")
done

# --- Run rsync ---
rsync -avz --delete "${EXCLUDE_PARAMS[@]}" "$LOCAL_DIR"  "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR"

echo "Sync complete!"
