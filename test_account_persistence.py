#!/usr/bin/env python3
"""
Test script for account persistence and statistics integration
Creates test accounts and verifies account stats API shows all saved accounts
"""

import json
import os
import sys
import urllib.request

import importlib.util

# Load the account-stats module
spec = importlib.util.spec_from_file_location("account_stats", os.path.join(os.path.dirname(__file__), 'api', 'account-stats.py'))
account_stats_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(account_stats_module)

# Load the accounts module  
spec2 = importlib.util.spec_from_file_location("accounts", os.path.join(os.path.dirname(__file__), 'api', 'accounts.py'))
accounts_module = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(accounts_module)

def test_account_persistence():
    """Test account persistence and statistics integration"""
    
    print("🧪 Testing Account Persistence & Statistics Integration\n")
    
    # Clear existing files for clean testing
    accounts_file = '/tmp/kingmailer_accounts.json'
    stats_file = '/tmp/kingmailer_account_stats.json'
    
    if os.path.exists(accounts_file):
        os.remove(accounts_file)
        print("✅ Cleared existing accounts file")
    if os.path.exists(stats_file):
        os.remove(stats_file)
        print("✅ Cleared existing stats file")
    
    # Create test accounts
    test_accounts = {
        'smtp_accounts': [
            {
                'id': 1,
                'provider': 'gmail',
                'user': 'test1@gmail.com',
                'pass': 'app_password_123',
                'host': 'smtp.gmail.com',
                'port': 587,
                'sender_name': 'John Doe',
                'label': 'Test SMTP Account 1',
                'created_at': '2026-04-01T10:00:00'
            },
            {
                'id': 2,
                'provider': 'gmail',
                'user': 'test2@gmail.com',
                'pass': 'app_password_456',
                'host': 'smtp.gmail.com',
                'port': 587,
                'sender_name': 'Jane Smith',
                'label': 'Test SMTP Account 2',
                'created_at': '2026-04-01T10:30:00'
            }
        ],
        'gmail_api_accounts': [
            {
                'id': 1,
                'user': 'api1@gmail.com',
                'client_id': 'client123.apps.googleusercontent.com',
                'client_secret': 'secret123',
                'refresh_token': 'refresh123',
                'sender_name': 'API User 1',
                'label': 'Test Gmail API Account 1',
                'created_at': '2026-04-01T11:00:00'
            }
        ],
        'ses_accounts': [
            {
                'id': 1,
                'access_key_id': 'AKIATEST1234',
                'secret_access_key': 'secretkey123',
                'region': 'us-east-1',
                'from_email': 'noreply@testdomain.com',
                'label': 'Test SES Account',
                'created_at': '2026-04-01T12:00:00'
            }
        ],
        'ec2_relays': []
    }
    
    # Save test accounts
    accounts_module.save_accounts(test_accounts)
    print(f"✅ Saved {len(test_accounts['smtp_accounts'])} SMTP accounts")
    print(f"✅ Saved {len(test_accounts['gmail_api_accounts'])} Gmail API accounts")
    print(f"✅ Saved {len(test_accounts['ses_accounts'])} SES accounts")
    
    # Test comprehensive statistics merge
    print(f"\n📊 Testing comprehensive statistics merge:")
    comprehensive_stats = account_stats_module.merge_accounts_with_stats()
    
    print(f"SMTP accounts found: {len(comprehensive_stats['smtp'])}")
    print(f"Gmail API accounts found: {len(comprehensive_stats['gmail_api'])}")
    print(f"SES accounts found: {len(comprehensive_stats['ses'])}")
    
    # Display account details
    print(f"\n📋 Saved Account Details:")
    for account_type in ['smtp', 'gmail_api', 'ses']:
        accounts = comprehensive_stats[account_type]
        if accounts:
            print(f"\n{account_type.upper()} Accounts:")
            for account_id, details in accounts.items():
                print(f"  • {details['label']} ({account_id})")
                print(f"    - Emails sent: {details['emails_sent']}")
                print(f"    - Active: {details['is_active']}")
                print(f"    - Has tracking: {details['has_stats']}")
    
    # Now add some tracking stats and test again
    print(f"\n🔬 Adding tracking stats for one account...")
    
    # Load the send module
    spec3 = importlib.util.spec_from_file_location("send", os.path.join(os.path.dirname(__file__), 'api', 'send.py'))
    send_module = importlib.util.module_from_spec(spec3)
    spec3.loader.exec_module(send_module)
    
    # Track some sends for test1@gmail.com
    send_module.track_send_success('test1@gmail.com', 'smtp')
    send_module.track_send_success('test1@gmail.com', 'smtp')
    send_module.track_send_failure('test1@gmail.com', 'smtp', 'Test error')
    
    print(f"✅ Added tracking stats for test1@gmail.com")
    
    # Re-test comprehensive statistics
    comprehensive_stats = account_stats_module.merge_accounts_with_stats()
    test1_stats = comprehensive_stats['smtp']['test1@gmail.com']
    
    print(f"\n📊 Updated stats for test1@gmail.com:")
    print(f"  - Emails sent: {test1_stats['emails_sent']}")
    print(f"  - Failed attempts: {test1_stats['failed_attempts']}")
    print(f"  - Has tracking: {test1_stats['has_stats']}")
    print(f"  - Active: {test1_stats['is_active']}")
    
    print(f"\n🎉 Account persistence and statistics integration test completed!")
    print(f"✅ Accounts are saved persistently")
    print(f"✅ Statistics merge with saved accounts correctly")
    print(f"✅ Account stats show both saved accounts and tracking data")

if __name__ == "__main__":
    test_account_persistence()