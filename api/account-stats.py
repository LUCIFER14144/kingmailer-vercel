"""
Account Statistics API Endpoint
Provides account stats, send counts, and status tracking
Also displays all saved SMTP/API accounts with their statistics
"""

import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler

def load_saved_accounts():
    """Load saved accounts from accounts storage"""
    try:
        accounts_file = '/tmp/kingmailer_accounts.json'
        if os.path.exists(accounts_file):
            with open(accounts_file, 'r') as f:
                return json.load(f)
    except:
        pass
    return {
        'smtp_accounts': [],
        'ses_accounts': [],
        'gmail_api_accounts': [],
        'ec2_relays': []
    }

def load_account_tracking_stats():
    """Load account tracking statistics"""
    try:
        stats_file = '/tmp/kingmailer_account_stats.json'
        if os.path.exists(stats_file):
            with open(stats_file, 'r') as f:
                return json.load(f)
    except:
        pass
    return {"smtp": {}, "gmail_api": {}, "ses": {}}

def merge_accounts_with_stats():
    """Merge saved accounts with their tracking statistics"""
    saved_accounts = load_saved_accounts()
    tracking_stats = load_account_tracking_stats()
    
    # Build comprehensive account statistics
    comprehensive_stats = {
        'smtp': {},
        'gmail_api': {},  
        'ses': {},
        'ec2': {}
    }
    
    # Add SMTP accounts
    for account in saved_accounts.get('smtp_accounts', []):
        account_id = account.get('user', 'unknown')
        stats = tracking_stats.get('smtp', {}).get(account_id, {})
        
        comprehensive_stats['smtp'][account_id] = {
            'account_id': account_id,
            'account_type': 'smtp',
            'label': account.get('label', 'SMTP Account'),
            'provider': account.get('provider', 'gmail'),
            'created_at': account.get('created_at', datetime.now().isoformat()),
            'emails_sent': stats.get('emails_sent', 0),
            'failed_attempts': stats.get('failed_attempts', 0),
            'total_failures': stats.get('total_failures', 0),
            'is_active': stats.get('is_active', True),
            'last_failure': stats.get('last_failure'),
            'has_stats': bool(stats)
        }
    
    # Add Gmail API accounts
    for account in saved_accounts.get('gmail_api_accounts', []):
        account_id = account.get('user', 'unknown')
        stats = tracking_stats.get('gmail_api', {}).get(account_id, {})
        
        comprehensive_stats['gmail_api'][account_id] = {
            'account_id': account_id,
            'account_type': 'gmail_api',
            'label': account.get('label', 'Gmail API Account'),
            'created_at': account.get('created_at', datetime.now().isoformat()),
            'emails_sent': stats.get('emails_sent', 0),
            'failed_attempts': stats.get('failed_attempts', 0),
            'total_failures': stats.get('total_failures', 0),
            'is_active': stats.get('is_active', True),
            'last_failure': stats.get('last_failure'),
            'has_stats': bool(stats)
        }
    
    # Add SES accounts
    for account in saved_accounts.get('ses_accounts', []):
        region = account.get('region', 'unknown')
        access_key = account.get('access_key_id', account.get('access_key', 'unknown'))
        account_id = f"{region}_{access_key[:8]}"
        stats = tracking_stats.get('ses', {}).get(account_id, {})
        
        comprehensive_stats['ses'][account_id] = {
            'account_id': account_id,
            'account_type': 'ses',
            'label': account.get('label', 'SES Account'),
            'region': region,
            'from_email': account.get('from_email', ''),
            'created_at': account.get('created_at', datetime.now().isoformat()),
            'emails_sent': stats.get('emails_sent', 0),
            'failed_attempts': stats.get('failed_attempts', 0),
            'total_failures': stats.get('total_failures', 0),
            'is_active': stats.get('is_active', True),
            'last_failure': stats.get('last_failure'),
            'has_stats': bool(stats)
        }
    
    # Add any tracking stats that don't have saved accounts (orphaned stats)
    for account_type in ['smtp', 'gmail_api', 'ses']:
        for account_id, stats in tracking_stats.get(account_type, {}).items():
            if account_id not in comprehensive_stats[account_type]:
                comprehensive_stats[account_type][account_id] = {
                    'account_id': account_id,
                    'account_type': account_type,
                    'label': f'Orphaned {account_type.upper()} ({account_id})',
                    'created_at': stats.get('created_at', datetime.now().isoformat()),
                    'emails_sent': stats.get('emails_sent', 0),
                    'failed_attempts': stats.get('failed_attempts', 0),
                    'total_failures': stats.get('total_failures', 0),
                    'is_active': stats.get('is_active', True),
                    'last_failure': stats.get('last_failure'),
                    'has_stats': True,
                    'is_orphaned': True
                }
    
    return comprehensive_stats

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Get comprehensive account statistics including saved accounts"""
        try:
            # Get comprehensive account statistics (saved accounts + tracking stats)
            account_stats = merge_accounts_with_stats()
            
            response_data = {
                "success": True,
                "accountStats": account_stats,
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total_accounts": sum(len(accounts) for accounts in account_stats.values()),
                    "total_emails_sent": sum(
                        sum(acc.get('emails_sent', 0) for acc in accounts.values()) 
                        for accounts in account_stats.values()
                    ),
                    "active_accounts": sum(
                        sum(1 for acc in accounts.values() if acc.get('is_active', True)) 
                        for accounts in account_stats.values()
                    ),
                    "deactivated_accounts": sum(
                        sum(1 for acc in accounts.values() if not acc.get('is_active', True)) 
                        for accounts in account_stats.values()
                    )
                }
            }
            
            # Set CORS headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
            
            self.wfile.write(json.dumps(response_data).encode())
            
        except Exception as e:
            # Error response
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            error_response = {
                "success": False,
                "error": str(e)
            }
            self.wfile.write(json.dumps(error_response).encode())

    def do_OPTIONS(self):
        """Handle preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()