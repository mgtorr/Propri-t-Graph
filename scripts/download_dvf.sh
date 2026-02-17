#!/usr/bin/env bash
# Download DVF data for specified departments and years
# Usage: ./download_dvf.sh [year] [dept1] [dept2] ...
# Example: ./download_dvf.sh 2023 75 69 13

set -euo pipefail

BASE_URL="https://files.data.gouv.fr/geo-dvf/latest/csv"
DATA_DIR="/data/raw/dvf"
YEAR="${1:-2023}"
shift || true
DEPTS="${@:-75 69 13 33 31 06 59 67 44 34}"

mkdir -p "$DATA_DIR/$YEAR"

echo "Downloading DVF data for year $YEAR..."
for dept in $DEPTS; do
    echo "  Dept $dept..."
    URL="$BASE_URL/$YEAR/departements/${dept}.csv.gz"
    OUTPUT="$DATA_DIR/$YEAR/${dept}.csv.gz"

    if [ -f "$OUTPUT" ]; then
        echo "  Already cached: $OUTPUT"
        continue
    fi

    if curl -sf -o "$OUTPUT" "$URL"; then
        SIZE=$(du -h "$OUTPUT" | cut -f1)
        echo "  Downloaded: $OUTPUT ($SIZE)"
    else
        echo "  WARNING: Not found: $URL (may not exist for $YEAR)"
        rm -f "$OUTPUT"
    fi
done

echo "Done! Run ingestion pipeline to load into PostgreSQL:"
echo "  docker compose run --rm dvf-ingestion"
