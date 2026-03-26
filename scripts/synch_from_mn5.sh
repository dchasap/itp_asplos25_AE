#!/bin/bash

# --- Configuration ---
REMOTE_USER=bsc018186
REMOTE_HOST=transfer1.bsc.es
REMOTE_DIR=/gpfs/scratch/bsc18/bsc018186/VMem
LOCAL_DIR=/home/bscuser/synched_mnt

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
rsync -avz "${EXCLUDE_PARAMS[@]}" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR" "$LOCAL_DIR"

echo "Sync complete!"
