#!/bin/bash

EXP_ID=$1
REMOTE="bsc018186@transfer1.bsc.es:/gpfs/scratch/bsc18/bsc018186/VMem/data/$EXP_ID"
LOCAL="./data/$EXP_ID"

mkdir -p "$LOCAL"

echo "Syncing experiment: $EXP_ID"

rsync -av \
  --include="*/" \
  --include="*.yaml" \
  --include="*.json" \
  --include="*.parquet" \
  --include="*.csv" \
  --include="*.png" \
  --include="*.pdf" \
  --exclude="*" \
  "$REMOTE/" \
  "$LOCAL/"