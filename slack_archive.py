#!/usr/bin/env python3
"""
Slack Channel Archive Tool - Production Version
Identifies and archives inactive channels based on acceptance criteria
"""

import os
import sys
import csv
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
import logging

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    print("Error: slack_sdk not installed. Please run: pip install slack-sdk")
    sys.exit(1)

def setup_logging(verbose: bool = False):
    """Configure logging with appropriate verbosity"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f'slack_archive_{timestamp}.log'
    
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")
    return logger

def load_channels_from_csv(csv_path: str, logger: logging.Logger) -> List[Dict]:
    """Load channels meeting archive criteria from CSV"""
    channels = []
    july_2_2025 = datetime(2025, 7, 2)
    
    protected_channels = {
        'general', 'random', 'announcements', 'compliance', 'team-tech',
        'fetch', 'collective-leads', 'team-marketing', 'team-devops'
    }
    
    stats = {'total': 0, 'skipped_private': 0, 'skipped_archived': 0, 
             'skipped_protected': 0, 'skipped_members': 0, 'skipped_active': 0, 
             'parse_errors': 0}
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row_num, row in enumerate(reader, 1):
                stats['total'] += 1
                
                try:
                    name = row['Name']
                    members = int(row['Members']) if row['Members'] else 0
                    last_activity_str = row['Last activity']
                    is_private = row.get('Private', '').lower() == 'true'
                    is_archived = row.get('Archived', '').lower() == 'true'
                    channel_id = row.get('ID', '')
                    
                    # Apply exclusion rules with tracking
                    if is_private:
                        stats['skipped_private'] += 1
                        logger.debug(f"Row {row_num}: Skipping private channel: {name}")
                        continue
                    
                    if is_archived:
                        stats['skipped_archived'] += 1
                        logger.debug(f"Row {row_num}: Skipping archived channel: {name}")
                        continue
                    
                    if name.lower() in protected_channels:
                        stats['skipped_protected'] += 1
                        logger.debug(f"Row {row_num}: Skipping protected channel: {name}")
                        continue
                    
                    if members > 4:
                        stats['skipped_members'] += 1
                        logger.debug(f"Row {row_num}: Skipping {name} - too many members ({members})")
                        continue
                    
                    # Parse last activity date
                    last_activity = datetime.strptime(last_activity_str.split(' -')[0], '%a, %d %b %Y %H:%M:%S')
                    
                    if last_activity >= july_2_2025:
                        stats['skipped_active'] += 1
                        logger.debug(f"Row {row_num}: Skipping {name} - recent activity ({last_activity.date()})")
                        continue
                    
                    channels.append({
                        'name': name,
                        'id': channel_id,
                        'members': members,
                        'last_activity': last_activity,
                        'days_inactive': (datetime.now() - last_activity).days
                    })
                    
                except (ValueError, KeyError) as e:
                    stats['parse_errors'] += 1
                    logger.warning(f"Row {row_num}: Parse error - {e}. Row data: {row}")
                    continue
                    
    except FileNotFoundError:
        logger.error(f"CSV file not found: {csv_path}")
        return []
    except Exception as e:
        logger.error(f"Error reading CSV: {e}")
        return []
    
    channels.sort(key=lambda x: (x['members'], -x['days_inactive']))
    
    logger.info(f"CSV Processing Stats: {stats}")
    logger.info(f"Channels meeting criteria: {len(channels)}")
    
    return channels

def get_team_tech_channel(client: WebClient, logger: logging.Logger) -> Optional[str]:
    """Find Team-Tech channel with pagination support"""
    try:
        cursor = None
        while True:
            params = {'types': 'public_channel', 'limit': 200}
            if cursor:
                params['cursor'] = cursor
            
            result = client.conversations_list(**params)
            
            for channel in result['channels']:
                if channel['name'].lower() == 'team-tech':
                    logger.info(f"Found Team-Tech channel: {channel['id']}")
                    return channel['id']
            
            cursor = result.get('response_metadata', {}).get('next_cursor')
            if not cursor:
                break
        
        logger.error("Team-Tech channel not found after checking all channels")
        return None
        
    except SlackApiError as e:
        logger.error(f"Error finding Team-Tech channel: {e.response['error']}")
        return None

def post_notification(client: WebClient, channels: List[Dict], logger: logging.Logger) -> bool:
    """Post 3-day warning notification to Team-Tech channel"""
    team_tech_id = get_team_tech_channel(client, logger)
    if not team_tech_id:
        return False
    
    try:
        archive_date = (datetime.now() + timedelta(days=3)).strftime('%B %d, %Y')
        opt_out_date = (datetime.now() + timedelta(days=2)).strftime('%B %d')
        
        message = f"""SLACK WORKSPACE CLEANUP - 3 DAY NOTICE

The following {len(channels)} channels will be archived on {archive_date}.

Channels meet both criteria:
- Four (4) or fewer members
- No activity between July 2 - August 2, 2025

Channels scheduled for archival:
"""
        
        for i, channel in enumerate(channels[:50], 1):
            last_active = channel['last_activity'].strftime('%b %d, %Y')
            message += f"{i}. #{channel['name']} ({channel['members']} members, last active: {last_active})\n"
        
        if len(channels) > 50:
            message += f"\n... and {len(channels) - 50} more channels\n"
        
        message += f"""
TO OPT-OUT:
Contact ITOps with the channel name by {opt_out_date}

Note: Channels will be archived (not deleted). All content remains accessible and can be unarchived if needed.
"""
        
        response = client.chat_postMessage(
            channel=team_tech_id,
            text=message,
            unfurl_links=False
        )
        
        logger.info(f"Notification posted successfully. Message timestamp: {response['ts']}")
        return True
        
    except SlackApiError as e:
        logger.error(f"Failed to post notification: {e.response['error']}")
        return False

def archive_channels(client: WebClient, channels: List[Dict], dry_run: bool, logger: logging.Logger) -> Dict:
    """Archive channels in batch with comprehensive error handling"""
    stats = {'processed': 0, 'successful': 0, 'failed': 0, 'skipped': 0}
    
    mode = "DRY RUN" if dry_run else "LIVE"
    logger.info(f"Starting {mode} archive of {len(channels)} channels")
    
    for channel in channels:
        stats['processed'] += 1
        channel_desc = f"#{channel['name']} ({channel['id']})"
        
        try:
            # Verify channel status
            info = client.conversations_info(channel=channel['id'])
            current_state = info['channel']
            
            if current_state['is_archived']:
                stats['skipped'] += 1
                logger.info(f"{channel_desc}: Already archived, skipping")
                continue
            
            # Update member count if changed
            current_members = current_state.get('num_members', 0)
            if current_members != channel['members']:
                logger.warning(f"{channel_desc}: Member count changed from {channel['members']} to {current_members}")
            
            if dry_run:
                print(f"[DRY RUN] Would archive: {channel_desc}")
                logger.info(f"[DRY RUN] Would archive: {channel_desc}")
                stats['successful'] += 1
            else:
                client.conversations_archive(channel=channel['id'])
                print(f"Archived: {channel_desc}")
                logger.info(f"Successfully archived: {channel_desc}")
                stats['successful'] += 1
                
        except SlackApiError as e:
            error_code = e.response['error']
            stats['failed'] += 1
            
            if error_code == 'channel_not_found':
                logger.warning(f"{channel_desc}: Channel not found")
            elif error_code == 'already_archived':
                stats['skipped'] += 1
                stats['failed'] -= 1
                logger.info(f"{channel_desc}: Already archived")
            elif error_code == 'cant_archive_general':
                logger.error(f"{channel_desc}: Cannot archive general channel")
            elif error_code == 'restricted_action':
                logger.error(f"{channel_desc}: Insufficient permissions")
            else:
                logger.error(f"{channel_desc}: Archive failed - {error_code}")
        
        except Exception as e:
            stats['failed'] += 1
            logger.error(f"{channel_desc}: Unexpected error - {e}")
        
        time.sleep(0.5)  # Rate limiting
    
    logger.info(f"{mode} archive complete. Stats: {stats}")
    return stats

def main():
    parser = argparse.ArgumentParser(description='Slack Channel Archive Tool')
    parser.add_argument('--csv', type=str, help='Path to CSV file')
    parser.add_argument('--token', type=str, help='Slack user token')
    parser.add_argument('--batch-size', type=int, default=50, help='Batch size (default: 50)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    logger = setup_logging(args.verbose)
    
    # Get CSV path
    csv_path = args.csv
    if not csv_path:
        csv_path = input("Enter CSV file path: ").strip()
        if not csv_path:
            csv_path = '/Users/jacobruffin/Downloads/channels_TCWQ899A6_20250828-105331_1.csv'
    
    if not os.path.exists(csv_path):
        logger.error(f"CSV file not found: {csv_path}")
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)
    
    # Load channels
    channels = load_channels_from_csv(csv_path, logger)
    print(f"\nIdentified {len(channels)} channels for archival")
    
    if not channels:
        print("No channels meet criteria")
        sys.exit(0)
    
    # Get authentication
    token = args.token or os.environ.get('SLACK_USER_TOKEN')
    if not token:
        print("Enter your Slack user token:")
        token = input().strip()
    
    if not token:
        logger.error("No token provided")
        print("Error: No token provided")
        sys.exit(1)
    
    client = WebClient(token=token)
    
    # Test authentication
    try:
        auth = client.auth_test()
        user_info = f"{auth['user']} in {auth['team']}"
        logger.info(f"Authenticated as: {user_info}")
        print(f"Authenticated as: {user_info}")
    except SlackApiError as e:
        logger.error(f"Authentication failed: {e.response['error']}")
        print(f"Authentication failed: {e.response['error']}")
        sys.exit(1)
    
    # Create batches
    batch_size = args.batch_size
    batch = channels[:batch_size]
    
    # Menu
    print(f"\nFirst batch: {len(batch)} channels")
    print("\nOptions:")
    print("1. Post 3-day notification to Team-Tech")
    print("2. Dry run")
    print("3. Archive channels (requires confirmation)")
    print("4. Exit")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == '1':
        print("Posting notification to Team-Tech...")
        if post_notification(client, batch, logger):
            print("Notification posted successfully")
        else:
            print("Failed to post notification")
    
    elif choice == '2':
        print(f"\nStarting dry run of {len(batch)} channels...")
        stats = archive_channels(client, batch, dry_run=True, logger=logger)
        print(f"\nDry run complete:")
        print(f"  Processed: {stats['processed']}")
        print(f"  Would archive: {stats['successful']}")
        print(f"  Already archived: {stats['skipped']}")
        print(f"  Errors: {stats['failed']}")
    
    elif choice == '3':
        print(f"\nWARNING: This will archive {len(batch)} channels")
        confirm = input("Type 'ARCHIVE' to confirm: ")
        if confirm == 'ARCHIVE':
            print(f"\nStarting archive of {len(batch)} channels...")
            stats = archive_channels(client, batch, dry_run=False, logger=logger)
            print(f"\nArchive complete:")
            print(f"  Processed: {stats['processed']}")
            print(f"  Archived: {stats['successful']}")
            print(f"  Skipped: {stats['skipped']}")
            print(f"  Failed: {stats['failed']}")
        else:
            print("Archive cancelled")
    
    logger.info("Process completed")
    print(f"\nLog file: slack_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

if __name__ == "__main__":
    main()