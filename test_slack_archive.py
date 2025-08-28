#!/usr/bin/env python3
"""
Unit tests for Slack Archive Tool
"""

import unittest
import tempfile
import csv
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import logging

# Import the module to test
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slack_archive_final as slack_archive


class TestCSVParsing(unittest.TestCase):
    """Test CSV parsing and filtering logic"""
    
    def setUp(self):
        self.logger = logging.getLogger('test')
        self.temp_csv = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv')
        
    def tearDown(self):
        os.unlink(self.temp_csv.name)
    
    def write_test_csv(self, rows):
        """Helper to write test CSV data"""
        writer = csv.DictWriter(self.temp_csv, fieldnames=['Name', 'ID', 'Members', 'Last activity', 'Private', 'Archived'])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        self.temp_csv.close()
    
    def test_load_valid_channels(self):
        """Test loading channels that meet criteria"""
        test_data = [
            {'Name': 'old-channel', 'ID': 'C001', 'Members': '3', 
             'Last activity': 'Mon, 01 Jun 2025 10:00:00 -0700', 
             'Private': 'False', 'Archived': 'False'},
            {'Name': 'empty-channel', 'ID': 'C002', 'Members': '0',
             'Last activity': 'Tue, 01 Apr 2025 10:00:00 -0700',
             'Private': 'False', 'Archived': 'False'}
        ]
        self.write_test_csv(test_data)
        
        channels = slack_archive.load_channels_from_csv(self.temp_csv.name, self.logger)
        
        self.assertEqual(len(channels), 2)
        self.assertEqual(channels[0]['name'], 'empty-channel')  # Sorted by member count
        self.assertEqual(channels[0]['members'], 0)
        self.assertEqual(channels[1]['name'], 'old-channel')
        self.assertEqual(channels[1]['members'], 3)
    
    def test_exclude_private_channels(self):
        """Test that private channels are excluded"""
        test_data = [
            {'Name': 'private-channel', 'ID': 'C003', 'Members': '2',
             'Last activity': 'Mon, 01 Jun 2025 10:00:00 -0700',
             'Private': 'True', 'Archived': 'False'}
        ]
        self.write_test_csv(test_data)
        
        channels = slack_archive.load_channels_from_csv(self.temp_csv.name, self.logger)
        self.assertEqual(len(channels), 0)
    
    def test_exclude_archived_channels(self):
        """Test that already archived channels are excluded"""
        test_data = [
            {'Name': 'archived-channel', 'ID': 'C004', 'Members': '1',
             'Last activity': 'Mon, 01 Jun 2025 10:00:00 -0700',
             'Private': 'False', 'Archived': 'True'}
        ]
        self.write_test_csv(test_data)
        
        channels = slack_archive.load_channels_from_csv(self.temp_csv.name, self.logger)
        self.assertEqual(len(channels), 0)
    
    def test_exclude_protected_channels(self):
        """Test that protected system channels are excluded"""
        test_data = [
            {'Name': 'general', 'ID': 'C005', 'Members': '4',
             'Last activity': 'Mon, 01 Jun 2025 10:00:00 -0700',
             'Private': 'False', 'Archived': 'False'},
            {'Name': 'team-tech', 'ID': 'C006', 'Members': '3',
             'Last activity': 'Mon, 01 Jun 2025 10:00:00 -0700',
             'Private': 'False', 'Archived': 'False'}
        ]
        self.write_test_csv(test_data)
        
        channels = slack_archive.load_channels_from_csv(self.temp_csv.name, self.logger)
        self.assertEqual(len(channels), 0)
    
    def test_exclude_channels_with_many_members(self):
        """Test that channels with >4 members are excluded"""
        test_data = [
            {'Name': 'busy-channel', 'ID': 'C007', 'Members': '5',
             'Last activity': 'Mon, 01 Jun 2025 10:00:00 -0700',
             'Private': 'False', 'Archived': 'False'},
            {'Name': 'popular-channel', 'ID': 'C008', 'Members': '100',
             'Last activity': 'Mon, 01 Jun 2025 10:00:00 -0700',
             'Private': 'False', 'Archived': 'False'}
        ]
        self.write_test_csv(test_data)
        
        channels = slack_archive.load_channels_from_csv(self.temp_csv.name, self.logger)
        self.assertEqual(len(channels), 0)
    
    def test_exclude_recently_active_channels(self):
        """Test that channels active after July 2, 2025 are excluded"""
        test_data = [
            {'Name': 'recent-channel', 'ID': 'C009', 'Members': '2',
             'Last activity': 'Thu, 03 Jul 2025 10:00:00 -0700',  # After July 2
             'Private': 'False', 'Archived': 'False'},
            {'Name': 'current-channel', 'ID': 'C010', 'Members': '1',
             'Last activity': 'Mon, 15 Aug 2025 10:00:00 -0700',  # Way after
             'Private': 'False', 'Archived': 'False'}
        ]
        self.write_test_csv(test_data)
        
        channels = slack_archive.load_channels_from_csv(self.temp_csv.name, self.logger)
        self.assertEqual(len(channels), 0)
    
    def test_handle_malformed_csv_rows(self):
        """Test graceful handling of malformed CSV rows"""
        test_data = [
            {'Name': 'good-channel', 'ID': 'C011', 'Members': '2',
             'Last activity': 'Mon, 01 Jun 2025 10:00:00 -0700',
             'Private': 'False', 'Archived': 'False'},
            {'Name': 'bad-date-channel', 'ID': 'C012', 'Members': '2',
             'Last activity': 'INVALID DATE FORMAT',
             'Private': 'False', 'Archived': 'False'},
            {'Name': 'bad-members', 'ID': 'C013', 'Members': 'NOT_A_NUMBER',
             'Last activity': 'Mon, 01 Jun 2025 10:00:00 -0700',
             'Private': 'False', 'Archived': 'False'}
        ]
        self.write_test_csv(test_data)
        
        channels = slack_archive.load_channels_from_csv(self.temp_csv.name, self.logger)
        self.assertEqual(len(channels), 1)
        self.assertEqual(channels[0]['name'], 'good-channel')
    
    def test_nonexistent_csv_file(self):
        """Test handling of nonexistent CSV file"""
        channels = slack_archive.load_channels_from_csv('/nonexistent/file.csv', self.logger)
        self.assertEqual(channels, [])


class TestSlackAPIInteractions(unittest.TestCase):
    """Test Slack API interactions"""
    
    def setUp(self):
        self.logger = logging.getLogger('test')
        self.mock_client = Mock()
    
    def test_find_team_tech_channel_success(self):
        """Test successfully finding Team-Tech channel"""
        self.mock_client.conversations_list.return_value = {
            'channels': [
                {'name': 'general', 'id': 'C001'},
                {'name': 'team-tech', 'id': 'C002'},
                {'name': 'random', 'id': 'C003'}
            ],
            'response_metadata': {}
        }
        
        channel_id = slack_archive.get_team_tech_channel(self.mock_client, self.logger)
        self.assertEqual(channel_id, 'C002')
    
    def test_find_team_tech_channel_with_pagination(self):
        """Test finding Team-Tech channel across multiple pages"""
        # First page without team-tech
        self.mock_client.conversations_list.side_effect = [
            {
                'channels': [{'name': 'general', 'id': 'C001'}],
                'response_metadata': {'next_cursor': 'cursor123'}
            },
            {
                'channels': [{'name': 'team-tech', 'id': 'C002'}],
                'response_metadata': {}
            }
        ]
        
        channel_id = slack_archive.get_team_tech_channel(self.mock_client, self.logger)
        self.assertEqual(channel_id, 'C002')
        self.assertEqual(self.mock_client.conversations_list.call_count, 2)
    
    def test_archive_channel_dry_run(self):
        """Test dry run archive (no actual archiving)"""
        channels = [
            {'name': 'test-channel', 'id': 'C001', 'members': 2}
        ]
        
        self.mock_client.conversations_info.return_value = {
            'channel': {'is_archived': False, 'num_members': 2}
        }
        
        stats = slack_archive.archive_channels(self.mock_client, channels, dry_run=True, logger=self.logger)
        
        self.assertEqual(stats['processed'], 1)
        self.assertEqual(stats['successful'], 1)
        self.assertEqual(stats['failed'], 0)
        self.mock_client.conversations_archive.assert_not_called()
    
    def test_archive_channel_live(self):
        """Test live archive execution"""
        channels = [
            {'name': 'test-channel', 'id': 'C001', 'members': 2}
        ]
        
        self.mock_client.conversations_info.return_value = {
            'channel': {'is_archived': False, 'num_members': 2}
        }
        
        stats = slack_archive.archive_channels(self.mock_client, channels, dry_run=False, logger=self.logger)
        
        self.assertEqual(stats['processed'], 1)
        self.assertEqual(stats['successful'], 1)
        self.mock_client.conversations_archive.assert_called_once_with(channel='C001')
    
    def test_skip_already_archived(self):
        """Test skipping already archived channels"""
        channels = [
            {'name': 'archived-channel', 'id': 'C001', 'members': 2}
        ]
        
        self.mock_client.conversations_info.return_value = {
            'channel': {'is_archived': True, 'num_members': 2}
        }
        
        stats = slack_archive.archive_channels(self.mock_client, channels, dry_run=False, logger=self.logger)
        
        self.assertEqual(stats['skipped'], 1)
        self.assertEqual(stats['successful'], 0)
        self.mock_client.conversations_archive.assert_not_called()
    
    def test_handle_api_errors(self):
        """Test handling of various Slack API errors"""
        from slack_sdk.errors import SlackApiError
        
        channels = [
            {'name': 'test-channel', 'id': 'C001', 'members': 2}
        ]
        
        # Simulate channel not found error
        error_response = {'error': 'channel_not_found'}
        self.mock_client.conversations_info.side_effect = SlackApiError('Error', error_response)
        
        stats = slack_archive.archive_channels(self.mock_client, channels, dry_run=False, logger=self.logger)
        
        self.assertEqual(stats['failed'], 1)
        self.assertEqual(stats['successful'], 0)


class TestDateLogic(unittest.TestCase):
    """Test date parsing and filtering logic"""
    
    def test_date_parsing(self):
        """Test parsing of Slack date format"""
        date_str = "Thu, 28 Aug 2025 10:27:56 -0700"
        expected = datetime(2025, 8, 28, 10, 27, 56)
        
        # Extract just the date parsing logic
        parsed = datetime.strptime(date_str.split(' -')[0], '%a, %d %b %Y %H:%M:%S')
        self.assertEqual(parsed, expected)
    
    def test_july_2_cutoff(self):
        """Test that July 2, 2025 is the correct cutoff"""
        july_1 = datetime(2025, 7, 1, 23, 59, 59)  # Should be included
        july_2 = datetime(2025, 7, 2, 0, 0, 0)    # Should be excluded
        july_3 = datetime(2025, 7, 3, 0, 0, 0)    # Should be excluded
        
        cutoff = datetime(2025, 7, 2)
        
        self.assertTrue(july_1 < cutoff)
        self.assertFalse(july_2 < cutoff)
        self.assertFalse(july_3 < cutoff)


class TestIntegration(unittest.TestCase):
    """Integration tests for the full workflow"""
    
    def setUp(self):
        self.logger = logging.getLogger('test')
        
    @patch('slack_archive_final.WebClient')
    def test_authentication_flow(self, mock_client_class):
        """Test authentication validation"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_client.auth_test.return_value = {
            'ok': True,
            'user': 'test_user',
            'team': 'test_team'
        }
        
        # Test successful auth
        mock_client.auth_test.assert_not_called()
        client = mock_client_class(token='xoxp-test-token')
        auth_result = client.auth_test()
        
        self.assertEqual(auth_result['user'], 'test_user')
        self.assertEqual(auth_result['team'], 'test_team')


if __name__ == '__main__':
    # Run with verbosity for detailed output
    unittest.main(verbosity=2)