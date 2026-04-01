"""
Account Statistics API Endpoint  
Provides account stats, send counts, and status tracking
Enhanced for Vercel serverless environment with better visibility
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
    except Exception as e:
        print(f"Error loading saved accounts: {e}")
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
    except Exception as e:
        print(f"Error loading tracking stats: {e}")
    return {"smtp": {}, "gmail_api": {}, "ses": {}}

def create_demo_accounts():
    """Create demo account data to show functionality even when no real accounts exist"""
    return {
        'smtp': {
            'demo_smtp_user@gmail.com': {
                'account_id': 'demo_smtp_user@gmail.com',
                'account_type': 'smtp',
                'label': 'Demo SMTP Account (Gmail)',
                'provider': 'gmail',
                'created_at': datetime.now().isoformat(),
                'emails_sent': 0,
                'failed_attempts': 0,
                'total_failures': 0,
                'is_active': True,
                'last_failure': None,
                'has_stats': False,
                'is_placeholder': True,
                'note': 'Add real SMTP accounts via Account Management to see actual stats'
            }
        },
        'gmail_api': {
            'demo_api@gmail.com': {
                'account_id': 'demo_api@gmail.com', 
                'account_type': 'gmail_api',
                'label': 'Demo Gmail API Account',
                'created_at': datetime.now().isoformat(),
                'emails_sent': 0,
                'failed_attempts': 0,
                'total_failures': 0,
                'is_active': True,
                'last_failure': None,
                'has_stats': False,
                'is_placeholder': True,
                'note': 'Add real Gmail API accounts via Account Management to see actual stats'
            }
        },
        'ses': {
            'us-east-1_demo': {
                'account_id': 'us-east-1_demo',
                'account_type': 'ses',
                'label': 'Demo SES Account',
                'region': 'us-east-1',
                'from_email': 'demo@example.com',
                'created_at': datetime.now().isoformat(),
                'emails_sent': 0,
                'failed_attempts': 0,
                'total_failures': 0,
                'is_active': True,
                'last_failure': None,
                'has_stats': False,
                'is_placeholder': True,
                'note': 'Add real SES accounts via Account Management to see actual stats'
            }
        },
        'ec2': {}
    }

def merge_accounts_with_stats():
    """Merge saved accounts with their tracking statistics"""
    saved_accounts = load_saved_accounts()
    tracking_stats = load_account_tracking_stats()
    
    print(f"[ACCOUNT-STATS] Loading accounts - SMTP: {len(saved_accounts.get('smtp_accounts', []))}, SES: {len(saved_accounts.get('ses_accounts', []))}, Gmail API: {len(saved_accounts.get('gmail_api_accounts', []))}")
    print(f"[ACCOUNT-STATS] Tracking stats - SMTP: {len(tracking_stats.get('smtp', {}))}, SES: {len(tracking_stats.get('ses', {}))}, Gmail API: {len(tracking_stats.get('gmail_api', {}))}")
    
    # Build comprehensive account statistics
    comprehensive_stats = {
        'smtp': {},
        'gmail_api': {},  
        'ses': {},
        'ec2': {}
    }
    
    has_real_accounts = False
    
    # Add SMTP accounts
    for account in saved_accounts.get('smtp_accounts', []):
        has_real_accounts = True
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
            'has_stats': bool(stats),
            'is_placeholder': False
        }
    
    # Add Gmail API accounts
    for account in saved_accounts.get('gmail_api_accounts', []):
        has_real_accounts = True
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
            'has_stats': bool(stats),
            'is_placeholder': False
        }
    
    # Add SES accounts
    for account in saved_accounts.get('ses_accounts', []):
        has_real_accounts = True
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
            'has_stats': bool(stats),
            'is_placeholder': False
        }
    
    # Add any tracking stats that don't have saved accounts (orphaned stats)
    for account_type in ['smtp', 'gmail_api', 'ses']:
        for account_id, stats in tracking_stats.get(account_type, {}).items():
            if account_id not in comprehensive_stats[account_type]:
                has_real_accounts = True
                comprehensive_stats[account_type][account_id] = {
                    'account_id': account_id,
                    'account_type': account_type,
                    'label': f'Active {account_type.upper()} ({account_id})',
                    'created_at': stats.get('created_at', datetime.now().isoformat()),
                    'emails_sent': stats.get('emails_sent', 0),
                    'failed_attempts': stats.get('failed_attempts', 0),
                    'total_failures': stats.get('total_failures', 0),
                    'is_active': stats.get('is_active', True),
                    'last_failure': stats.get('last_failure'),
                    'has_stats': True,
                    'is_orphaned': True,
                    'is_placeholder': False
                }
    
    # If no real accounts exist, show demo accounts to demonstrate functionality
    if not has_real_accounts:
        print("[ACCOUNT-STATS] No real accounts found, showing demo accounts")
        demo_accounts = create_demo_accounts()
        for account_type, accounts in demo_accounts.items():
            comprehensive_stats[account_type].update(accounts)
    
    return comprehensive_stats

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Get comprehensive account statistics including saved accounts"""
        try:
            # Get comprehensive account statistics (saved accounts + tracking stats)
            account_stats = merge_accounts_with_stats()
            
            # Calculate summary statistics
            total_accounts = sum(len(accounts) for accounts in account_stats.values())
            total_emails_sent = sum(
                sum(acc.get('emails_sent', 0) for acc in accounts.values()) 
                for accounts in account_stats.values()
            )
            active_accounts = sum(
                sum(1 for acc in accounts.values() if acc.get('is_active', True)) 
                for accounts in account_stats.values()
            )
            deactivated_accounts = sum(
                sum(1 for acc in accounts.values() if not acc.get('is_active', True)) 
                for accounts in account_stats.values()
            )
            
            accounts_with_stats = sum(
                sum(1 for acc in accounts.values() if acc.get('has_stats', False)) 
                for accounts in account_stats.values()
            )
            
            placeholder_accounts = sum(
                sum(1 for acc in accounts.values() if acc.get('is_placeholder', False)) 
                for accounts in account_stats.values()
            )
            
            response_data = {
                "success": True,
                "accountStats": account_stats,
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total_accounts": total_accounts,
                    "total_emails_sent": total_emails_sent,
                    "active_accounts": active_accounts,
                    "deactivated_accounts": deactivated_accounts,
                    "accounts_with_tracking": accounts_with_stats,
                    "placeholder_accounts": placeholder_accounts,
                    "account_breakdown": {
                        "smtp": len(account_stats['smtp']),
                        "gmail_api": len(account_stats['gmail_api']),
                        "ses": len(account_stats['ses']),
                        "ec2": len(account_stats['ec2'])
                    }
                },
                "debug": {
                    "serverless_note": "In Vercel serverless environment, account data may not persist between requests",
                    "turbo_mode_enabled": True,
                    "account_deactivation_enabled": True,
                    "tracking_system_active": True
                }
            }
            
            # Set CORS headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
            
            response_json = json.dumps(response_data, indent=2)
            self.wfile.write(response_json.encode())
            
            print(f"[ACCOUNT-STATS] ✅ Returned {total_accounts} accounts ({active_accounts} active, {deactivated_accounts} deactivated)")
            
        except Exception as e:
            print(f"[ACCOUNT-STATS] ❌ Error: {str(e)}")
            # Error response
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            error_response = {
                "success": False,
                "error": str(e),
                "debug": "Account stats API error"
            }
            self.wfile.write(json.dumps(error_response).encode())

    def do_OPTIONS(self):
        """Handle preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
    def do_POST(self):
        """Handle POST requests for account management integration"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            action = data.get('action')
            
            if action == 'sync_accounts':
                # Force refresh of account statistics
                account_stats = merge_accounts_with_stats()
                
                response_data = {
                    "success": True,
                    "message": "Account statistics synchronized",
                    "accountStats": account_stats,
                    "timestamp": datetime.now().isoformat()
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                self.wfile.write(json.dumps(response_data, indent=2).encode())
                print("[ACCOUNT-STATS] ✅ Accounts synchronized via POST request")
                
            elif action == 'reactivate_account':
                # Reactivate a deactivated account
                account_id = data.get('account_id')
                account_type = data.get('account_type')
                
                if not account_id or not account_type:
                    raise ValueError("Account ID and type are required for reactivation")
                
                # Load current tracking stats
                tracking_stats = load_account_tracking_stats()
                
                # Reactivate the account
                if account_type in tracking_stats and account_id in tracking_stats[account_type]:
                    tracking_stats[account_type][account_id]['is_active'] = True
                    tracking_stats[account_type][account_id]['failed_attempts'] = 0
                    tracking_stats[account_type][account_id]['last_failure'] = None
                    
                    # Save updated stats
                    try:
                        stats_file = '/tmp/kingmailer_account_stats.json'
                        with open(stats_file, 'w') as f:
                            json.dump(tracking_stats, f, indent=2)
                    except Exception as e:
                        print(f"Error saving reactivated account stats: {e}")
                    
                    response_data = {
                        "success": True,
                        "message": f"Account {account_id} ({account_type}) has been reactivated",
                        "account_id": account_id,
                        "account_type": account_type
                    }
                    
                    print(f"[ACCOUNT-STATS] ✅ Reactivated {account_type} account: {account_id}")
                else:
                    response_data = {
                        "success": True,
                        "message": f"Account {account_id} ({account_type}) was not found in tracking stats (may not have been used yet)",
                        "account_id": account_id,
                        "account_type": account_type
                    }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                self.wfile.write(json.dumps(response_data, indent=2).encode())
                
            else:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                error_response = {
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "supported_actions": ["sync_accounts", "reactivate_account"]
                }
                self.wfile.write(json.dumps(error_response).encode())
                
        except Exception as e:
            print(f"[ACCOUNT-STATS] ❌ POST Error: {str(e)}")
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            error_response = {
                "success": False,
                "error": str(e),
                "debug": "Account stats POST API error"
            }
            self.wfile.write(json.dumps(error_response).encode())