#!/usr/bin/env python3
"""
Test script for account tracking functionality
Tests the account tracking functions to ensure proper failure tracking and deactivation
"""

import json
import os
import sys
import tempfile

# Add the API directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))

# Import tracking functions from send.py
from send import (
    load_account_stats,
    save_account_stats,
    track_send_success,
    track_send_failure,
    is_account_active
)

def test_account_tracking():
    """Test the account tracking system"""
    
    print("🧪 Testing Account Tracking System\n")
    
    # Clear existing stats for testing
    stats_file = '/tmp/kingmailer_account_stats.json'
    if os.path.exists(stats_file):
        os.remove(stats_file)
        print("✅ Cleared existing stats file")
    
    # Test account IDs
    smtp_account = "test_user@gmail.com"
    gmail_account = "test_gmail@gmail.com" 
    ses_account = "us-east-1_AKIAI123"
    
    print(f"\n📧 Testing SMTP Account: {smtp_account}")
    print(f"📧 Testing Gmail API Account: {gmail_account}")
    print(f"📧 Testing SES Account: {ses_account}")
    
    # Test initial state - all accounts should be active
    print("\n🔍 Initial Account Status:")
    print(f"SMTP Active: {is_account_active(smtp_account, 'smtp')}")
    print(f"Gmail Active: {is_account_active(gmail_account, 'gmail_api')}")
    print(f"SES Active: {is_account_active(ses_account, 'ses')}")
    
    # Test successful sends
    print("\n✅ Testing Successful Sends:")
    for i in range(5):
        track_send_success(smtp_account, 'smtp')
        track_send_success(gmail_account, 'gmail_api')
        track_send_success(ses_account, 'ses')
        print(f"Send {i+1} tracked successfully")
    
    # Check stats after successful sends
    stats = load_account_stats()
    print(f"\n📊 Stats after 5 successful sends:")
    print(f"SMTP: {json.dumps(stats.get('smtp', {}).get(smtp_account, {}), indent=2)}")
    print(f"Gmail: {json.dumps(stats.get('gmail_api', {}).get(gmail_account, {}), indent=2)}")
    print(f"SES: {json.dumps(stats.get('ses', {}).get(ses_account, {}), indent=2)}")
    
    # Test failures (should not trigger deactivation until 3 consecutive failures)
    print("\n❌ Testing First Two Failures (should remain active):")
    track_send_failure(smtp_account, 'smtp', 'Test error 1')
    track_send_failure(smtp_account, 'smtp', 'Test error 2')
    print(f"SMTP Active after 2 failures: {is_account_active(smtp_account, 'smtp')}")
    
    # Test third failure (should trigger deactivation)
    print("\n🚨 Testing Third Consecutive Failure (should deactivate):")
    track_send_failure(smtp_account, 'smtp', 'Daily user sending limit exceeded')
    print(f"SMTP Active after 3 failures: {is_account_active(smtp_account, 'smtp')}")
    
    # Test that success resets failure count
    print("\n🔄 Testing Failure Reset with Success:")
    track_send_failure(gmail_account, 'gmail_api', 'Test error 1')
    track_send_failure(gmail_account, 'gmail_api', 'Test error 2')
    print(f"Gmail Active after 2 failures: {is_account_active(gmail_account, 'gmail_api')}")
    
    # Add a success (should reset)
    track_send_success(gmail_account, 'gmail_api')
    print(f"Gmail Active after success (reset): {is_account_active(gmail_account, 'gmail_api')}")
    
    # Add 3 more failures (should deactivate)
    track_send_failure(gmail_account, 'gmail_api', 'Test error 3')
    track_send_failure(gmail_account, 'gmail_api', 'Test error 4')
    track_send_failure(gmail_account, 'gmail_api', 'Test error 5')
    print(f"Gmail Active after 3 new failures: {is_account_active(gmail_account, 'gmail_api')}")
    
    # Final stats
    stats = load_account_stats()
    print(f"\n📊 Final Statistics:")
    print(json.dumps(stats, indent=2))
    
    print("\n🎉 Account tracking test completed!")

if __name__ == "__main__":
    test_account_tracking()