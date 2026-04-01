"""
Test Gmail API integration before deployment.

Usage:
1. Get OAuth2 credentials from Google Cloud Console:
   - Go to https://console.cloud.google.com/apis/credentials
   - Create OAuth 2.0 Client ID (Desktop app type)
   - Download credentials JSON
   - Get access_token and refresh_token using OAuth2 flow
   
2. Set environment variables or edit this script with your credentials
3. Run: python test_gmail_api.py
"""

import json
import sys
import os

# Test configuration
TEST_CONFIG = {
    'gmail_config': {
        'user': 'your-email@gmail.com',  # Replace with your Gmail address
        'access_token': 'ya29.xxx',  # Replace with your access token
        'refresh_token': '1//xxx',  # Replace with your refresh token
        'client_id': 'xxx.apps.googleusercontent.com',  # Replace with your client ID
        'client_secret': 'xxx',  # Replace with your client secret
        'sender_name': 'Test Sender'
    },
    'to_email': 'recipient@example.com',  # Replace with test recipient
    'subject': 'Gmail API Test',
    'html_body': '<h1>Test Email</h1><p>This is a test email sent via Gmail API.</p>',
    'from_name': 'Test Sender'
}

def test_direct_gmail_api():
    """Test direct Gmail API sending"""
    print("🧪 Testing direct Gmail API send...")
    print(f"   From: {TEST_CONFIG['gmail_config']['user']}")
    print(f"   To: {TEST_CONFIG['to_email']}")
    print(f"   Subject: {TEST_CONFIG['subject']}")
    
    # Import the send module
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))
    from send import send_via_gmail_api
    
    try:
        result = send_via_gmail_api(
            gmail_config=TEST_CONFIG['gmail_config'],
            from_name=TEST_CONFIG['from_name'],
            to_email=TEST_CONFIG['to_email'],
            subject=TEST_CONFIG['subject'],
            html_body=TEST_CONFIG['html_body'],
            attachment=None,
            header_opts={}
        )
        
        if result.get('success'):
            print(f"   ✅ Success! Message ID: {result.get('message_id')}")
            return True
        else:
            print(f"   ❌ Failed: {result.get('error')}")
            if result.get('needs_refresh'):
                print(f"   ⚠️  Access token expired - needs refresh")
            return False
            
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_ec2_gmail_api():
    """Test EC2 relay + Gmail API (requires running EC2 instance)"""
    print("\n🧪 Testing EC2 relay + Gmail API...")
    
    ec2_url = os.getenv('EC2_RELAY_URL', 'http://your-ec2-ip:3000/relay')
    if 'your-ec2-ip' in ec2_url:
        print("   ⚠️  Skipping - EC2_RELAY_URL not configured")
        print("   Set EC2_RELAY_URL environment variable to test EC2 relay")
        return None
    
    print(f"   EC2 URL: {ec2_url}")
    
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))
    from send import send_via_ec2_gmail_api
    
    try:
        result = send_via_ec2_gmail_api(
            ec2_url=ec2_url,
            gmail_config=TEST_CONFIG['gmail_config'],
            from_name=TEST_CONFIG['from_name'],
            to_email=TEST_CONFIG['to_email'],
            subject=TEST_CONFIG['subject'],
            html_body=TEST_CONFIG['html_body'],
            attachment=None,
            header_opts={}
        )
        
        if result.get('success'):
            print(f"   ✅ Success! EC2 IP: {result.get('ec2_ip')}")
            return True
        else:
            print(f"   ❌ Failed: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"   ❌ Exception: {str(e)}")
        return False

def validate_config():
    """Validate test configuration before running"""
    print("📋 Validating configuration...")
    
    issues = []
    
    if 'your-email@gmail.com' in TEST_CONFIG['gmail_config']['user']:
        issues.append("gmail_config.user not configured")
    
    if 'ya29.xxx' in TEST_CONFIG['gmail_config']['access_token']:
        issues.append("gmail_config.access_token not configured")
    
    if 'recipient@example.com' in TEST_CONFIG['to_email']:
        issues.append("to_email not configured")
    
    if issues:
        print("\n❌ Configuration incomplete:")
        for issue in issues:
            print(f"   - {issue}")
        print("\n📝 Edit test_gmail_api.py and replace placeholder values with your credentials")
        print("\n💡 To get OAuth2 credentials:")
        print("   1. Visit https://console.cloud.google.com/apis/credentials")
        print("   2. Create OAuth 2.0 Client ID (Desktop app)")
        print("   3. Use OAuth2 playground or gcloud to get tokens")
        return False
    
    print("   ✅ Configuration looks good")
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("Gmail API Integration Test")
    print("=" * 60)
    print()
    
    if not validate_config():
        sys.exit(1)
    
    # Test direct Gmail API
    direct_success = test_direct_gmail_api()
    
    # Test EC2 relay (optional)
    ec2_success = test_ec2_gmail_api()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Direct Gmail API: {'✅ PASS' if direct_success else '❌ FAIL'}")
    if ec2_success is not None:
        print(f"EC2 + Gmail API: {'✅ PASS' if ec2_success else '❌ FAIL'}")
    else:
        print(f"EC2 + Gmail API: ⏭️  SKIPPED")
    print()
    
    if direct_success:
        print("🎉 Gmail API integration is working!")
        print("✅ Ready to deploy to production")
    else:
        print("⚠️  Fix the issues above before deploying")
        sys.exit(1)
