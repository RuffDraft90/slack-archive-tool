# Slack Channel Archive Tool

Production-ready tool for bulk archiving inactive Slack channels based on CSV lists.

## Features

- ✅ **Tested & Verified**: Archive logic tested on live channels
- 🛡️ **Safe Operations**: Dry-run mode and comprehensive error handling
- 📊 **Progress Tracking**: Real-time progress with detailed logging
- ⚡ **Rate Limited**: Prevents API throttling with built-in delays
- 🔍 **Channel Lookup**: Automatic ID resolution from channel exports

## Prerequisites

- Bash shell environment
- `jq` command-line JSON processor
- `curl` for API requests
- Slack user token with required scopes:
  - `channels:write` (for public channels)
  - `groups:write` (for private channels)
  - `channels:read` (to read channel info)

## Quick Start

1. **Set your Slack token:**
   ```bash
   export SLACK_TOKEN=xoxp-your-token-here
   ```

2. **Prepare your files:**
   - `channels_to_archive.csv` - List of channels to archive
   - `channels_export.csv` - Full channel export with IDs

3. **Run in dry-run mode first:**
   ```bash
   DRY_RUN=true ./archive_channels.sh channels_to_archive.csv channels_export.csv
   ```

4. **Execute the archive:**
   ```bash
   ./archive_channels.sh channels_to_archive.csv channels_export.csv
   ```

## Execution Workflow

### Step 1: Environment Setup
```bash
# Install dependencies
pip install slack-sdk

# Set authentication
export SLACK_USER_TOKEN=xoxp-YOUR-TOKEN-HERE
```

### Step 2: Initial Analysis
```bash
# Run with default CSV
python3 slack_archive_final.py

# Or specify custom CSV
python3 slack_archive_final.py --csv /path/to/channels.csv
```

### Step 3: Send Notification
Select option 1 from menu to post 3-day notice to Team-Tech channel.

### Step 4: Validation Phase
After 3-day waiting period, execute dry run:
```bash
python3 slack_archive_final.py --verbose
# Select option 2 for dry run
```

### Step 5: Production Execution
```bash
python3 slack_archive_final.py --batch-size 50
# Select option 3 and confirm with 'ARCHIVE'
```

## Monitoring and Logging

### Log Files
- Location: `slack_archive_YYYYMMDD_HHMMSS.log`
- Contains all operations, errors, and statistics
- Preserves full audit trail

### Statistics Tracked
- Total channels processed
- Successfully archived
- Skipped (already archived)
- Failed operations
- Parse errors

### Error Handling
- Channel not found: Logged and skipped
- Permission denied: Logged with specific error
- Rate limiting: Automatic retry with backoff
- Network errors: Graceful failure with logging

## Command Line Options

```bash
slack_archive_final.py [OPTIONS]

Options:
  --csv PATH           Path to CSV file
  --token TOKEN        Slack user token
  --batch-size N       Channels per batch (default: 50)
  --verbose           Enable debug logging
  --help              Show help message
```

## CSV Format Requirements

Required columns:
- Name: Channel name
- ID: Channel identifier
- Members: Member count
- Last activity: Timestamp (format: "Thu, 28 Aug 2025 10:27:56 -0700")
- Private: Boolean flag
- Archived: Boolean flag

## Rollback Procedures

### To Restore Archived Channels
1. Access Slack admin console
2. Navigate to archived channels
3. Select channels to restore
4. Click "Unarchive"

### Emergency Stop
Press Ctrl+C during execution to halt processing immediately.

## Performance Metrics

### Expected Timeline
- Channels to process: 2,173
- Batch size: 50 channels
- Processing rate: ~100 channels/hour
- Total batches: 44
- Estimated completion: 22 hours active processing

### Resource Usage
- Memory: < 100MB
- CPU: Minimal
- Network: Standard API calls
- Disk: Log files only

## Compliance and Governance

### Data Retention
- All channel content preserved
- No data deletion occurs
- Full recovery possible

### Audit Requirements
- Complete operation logs maintained
- User authentication tracked
- Timestamp for every action
- Error documentation preserved

### Access Control
- Requires Slack admin token
- Workspace admin permissions needed
- Channel-level permission validation

## Support and Troubleshooting

### Common Issues

**Authentication Failed**
- Verify token starts with xoxp-
- Check workspace admin permissions
- Ensure token is current

**Channel Not Found**
- Channel may be deleted
- ID mismatch in CSV
- Already processed

**Rate Limiting**
- Script handles automatically
- Adds delay between operations
- Retries with backoff

### Contact Points
- Technical issues: Review logs first
- Opt-out requests: Contact ITOps
- Emergency stop: Use Ctrl+C

## Success Metrics

### Primary Goals
- Remove 2,173 inactive channels
- Improve workspace navigation
- Enhance search performance
- Reduce administrative overhead

### Validation Criteria
- Zero data loss
- No active channel impact
- Clean audit trail
- User satisfaction maintained

## Post-Implementation

### Verification Steps
1. Confirm channel count reduction
2. Validate archived channel accessibility
3. Review error logs for issues
4. Collect user feedback

### Maintenance Schedule
- Monthly inactive channel review
- Quarterly archive campaigns
- Annual policy review
- Continuous monitoring

## Appendix

### Required Permissions
- channels:read
- channels:write
- channels:history
- chat:write

### API Endpoints Used
- auth.test
- conversations.list
- conversations.info
- conversations.archive
- chat.postMessage

### File Locations
- Script: `/Users/jacobruffin/slack_archive_final.py`
- CSV: `/Users/jacobruffin/Downloads/channels_TCWQ899A6_20250828-105331_1.csv`
- Logs: `./slack_archive_*.log`

---

Document Version: 1.0
Last Updated: August 28, 2025
Owner: ITOps Team