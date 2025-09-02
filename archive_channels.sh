#!/usr/bin/env bash
# archive_channels.sh - Production Slack Channel Archive Tool
# Simple approach: User batch of 50 OR CSV processing with batches of 50

set -euo pipefail

# Configuration
: "${SLACK_TOKEN:?SLACK_TOKEN env var is required (user token with proper scopes)}"
MODE="${1:-batch}"  # 'csv' (process from CSV) or 'batch' (user-defined 50 channels)
LOGFILE="archive_log_$(date +%Y%m%d_%H%M%S).log"
DRY_RUN="${DRY_RUN:-false}"

# File paths for CSV mode
CSV_TO_ARCHIVE="${CSV_TO_ARCHIVE:-channels_to_archive.csv}"
CSV_MASTER_LIST="${CSV_MASTER_LIST:-channels_E06G9S71G3E_20250902-154146_1.csv}"

echo "🚀 Slack Channel Archive Tool - Production"
echo "==========================================="
echo "🔧 Mode: $MODE"
echo "📝 Log File: $LOGFILE"
echo "🛡️  Dry Run Mode: $DRY_RUN"
echo ""

# User-defined batch of 50 channels - Format: "CHANNEL_ID:CHANNEL_NAME" 
USER_BATCH_50=(
    # Users populate this with exactly 50 channels they want to archive
    # Example: "C095P5R1RFS:ob-reminders"
    # TODO: User adds their 50 channel IDs here
)

# Validate mode
if [[ "$MODE" == "csv" ]]; then
    echo "📋 CSV MODE: Process channels from CSV files in batches of 50"
    echo "📁 Archive List: $CSV_TO_ARCHIVE"
    echo "📋 Master List: $CSV_MASTER_LIST"
    
    if [[ ! -f "$CSV_TO_ARCHIVE" ]]; then
        echo "❌ ERROR: Archive list file not found: $CSV_TO_ARCHIVE" >&2
        exit 1
    fi
    
    if [[ ! -f "$CSV_MASTER_LIST" ]]; then
        echo "❌ ERROR: Master list file not found: $CSV_MASTER_LIST" >&2
        exit 1
    fi
elif [[ "$MODE" == "batch" ]]; then
    if [[ ${#USER_BATCH_50[@]} -eq 0 ]]; then
        echo "⚠️  WARNING: USER_BATCH_50[] array is empty!"
        echo "   Please populate it with up to 50 channel IDs in the script"
        exit 1
    fi
    echo "📦 BATCH MODE: Process ${#USER_BATCH_50[@]} user-defined channels"
else
    echo "❌ ERROR: Invalid mode '$MODE'. Use 'csv' or 'batch'" >&2
    exit 1
fi

# Archive function with comprehensive error handling
archive_channel() {
    local channel_name="$1"
    local channel_id="$2"
    
    echo "[$(date '+%H:%M:%S')] Processing: $channel_name ($channel_id)" | tee -a "$LOGFILE"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  [DRY RUN] Would archive channel: $channel_id" | tee -a "$LOGFILE"
        return 0
    fi
    
    local resp
    resp=$(curl -sS -X POST "https://slack.com/api/conversations.archive" \
        -H "Authorization: Bearer ${SLACK_TOKEN}" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "channel=${channel_id}")
    
    local ok
    ok=$(echo "$resp" | jq -r '.ok // false')
    
    if [[ "$ok" == "true" ]]; then
        echo "  ✅ SUCCESS: Archived $channel_name" | tee -a "$LOGFILE"
        return 0
    fi
    
    local error
    error=$(echo "$resp" | jq -r '.error // "unknown_error"')
    
    case "$error" in
        "already_archived")
            echo "  ✅ ALREADY ARCHIVED: $channel_name" | tee -a "$LOGFILE"
            return 0
            ;;
        "channel_not_found")
            echo "  ⚠️  CHANNEL NOT FOUND: $channel_name (may have been deleted)" | tee -a "$LOGFILE"
            return 0
            ;;
        "missing_scope")
            echo "  ❌ PERMISSION ERROR: $channel_name - Missing required scope" | tee -a "$LOGFILE"
            return 1
            ;;
        *)
            echo "  ❌ FAILED: $channel_name - $error" | tee -a "$LOGFILE"
            return 1
            ;;
    esac
}

# Process user-defined batch of 50
process_user_batch() {
    local total_channels=${#USER_BATCH_50[@]}
    local current=0
    local success_count=0
    local fail_count=0
    
    echo "📦 Processing User Batch ($total_channels channels)"
    echo "=============================================="
    
    for channel_entry in "${USER_BATCH_50[@]}"; do
        ((current++))
        
        # Parse channel_id:channel_name format
        if [[ "$channel_entry" =~ ^([^:]+):(.+)$ ]]; then
            local channel_id="${BASH_REMATCH[1]}"
            local channel_name="${BASH_REMATCH[2]}"
        else
            echo "❌ INVALID FORMAT: $channel_entry (expected ID:NAME)" | tee -a "$LOGFILE"
            ((fail_count++))
            continue
        fi
        
        echo "[$current/$total_channels] Processing: $channel_name -> $channel_id"
        
        if archive_channel "$channel_name" "$channel_id"; then
            ((success_count++))
        else
            ((fail_count++))
        fi
        
        # Rate limiting
        sleep 0.5
    done
    
    echo ""
    echo "📈 BATCH RESULTS:"
    echo "   ✅ Successful: $success_count"
    echo "   ❌ Failed: $fail_count"
}

# Process CSV in batches of 50 with user confirmation
process_csv_batches() {
    local total_channels=$(tail -n +3 "$CSV_TO_ARCHIVE" | wc -l | tr -d ' ')
    local batch_size=50
    local batch_number=1
    local processed=0
    
    echo "📊 Total channels to process: $total_channels"
    echo "📦 Processing in batches of $batch_size with user confirmation"
    echo "=============================================="
    
    # Process channels from CSV in batches of 50
    tail -n +3 "$CSV_TO_ARCHIVE" | while IFS=',' read -r channel_name rest; do
        # Skip empty lines
        [[ -z "$channel_name" ]] && continue
        
        # Start new batch
        if (( processed % batch_size == 0 )); then
            if (( processed > 0 )); then
                echo ""
                echo "📈 Batch $((batch_number - 1)) completed!"
                echo ""
            fi
            
            echo "📦 BATCH $batch_number (channels $((processed + 1)) - $((processed + batch_size)))"
            echo "=============================================="
            
            if [[ "$DRY_RUN" != "true" ]]; then
                echo "⚠️  Ready to archive next batch of $batch_size channels"
                echo "   Type 'yes' to continue, 'skip' to skip this batch, or 'quit' to stop:"
                read -r confirmation
                
                case "$confirmation" in
                    "yes"|"YES"|"y"|"Y")
                        echo "✅ Proceeding with batch $batch_number..."
                        ;;
                    "skip"|"SKIP"|"s"|"S")
                        echo "⏭️  Skipping batch $batch_number..."
                        # Skip this entire batch
                        for ((i = 0; i < batch_size && processed < total_channels; i++)); do
                            ((processed++))
                        done
                        ((batch_number++))
                        continue
                        ;;
                    "quit"|"QUIT"|"q"|"Q")
                        echo "🛑 User requested quit. Stopping..."
                        exit 0
                        ;;
                    *)
                        echo "❌ Invalid response. Skipping batch $batch_number..."
                        for ((i = 0; i < batch_size && processed < total_channels; i++)); do
                            ((processed++))
                        done
                        ((batch_number++))
                        continue
                        ;;
                esac
            fi
            
            ((batch_number++))
        fi
        
        ((processed++))
        
        # Find channel ID from master list
        channel_id=$(grep "^$channel_name," "$CSV_MASTER_LIST" | cut -d',' -f2 | head -1 | tr -d '\r')
        
        if [[ -z "$channel_id" ]]; then
            echo "[$processed/$total_channels] ❌ SKIP: $channel_name (ID not found)" | tee -a "$LOGFILE"
            continue
        fi
        
        echo "[$processed/$total_channels] Processing: $channel_name -> $channel_id"
        archive_channel "$channel_name" "$channel_id"
        
        # Rate limiting
        sleep 0.5
    done
    
    echo ""
    echo "📈 ALL CSV BATCHES COMPLETED"
}

# Main execution
if [[ "$MODE" == "batch" ]]; then
    process_user_batch
elif [[ "$MODE" == "csv" ]]; then
    process_csv_batches
fi

echo ""
echo "=============================================="
echo "📝 Full log: $LOGFILE"

if [[ "$DRY_RUN" == "true" ]]; then
    echo "🛡️  DRY RUN COMPLETE - No channels were actually archived"
    echo "   To run for real, set: DRY_RUN=false"
else
    echo "🎉 ARCHIVE OPERATION COMPLETE"
fi

echo ""
echo "💡 Usage Examples:"
echo "   User Batch (50 channels):     ./archive_channels.sh batch"
echo "   CSV Batches (with confirms):  ./archive_channels.sh csv"  
echo "   Dry Run:                      DRY_RUN=true ./archive_channels.sh batch"
echo ""
echo "📝 For batch mode: Populate USER_BATCH_50[] array with your 50 channel IDs"