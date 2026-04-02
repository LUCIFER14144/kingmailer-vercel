"""
Account Statistics API Endpoint  
Provides account stats, send counts, and status tracking - FIXED VERSION
"""

import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler

def load_saved_accounts():
    """Load saved accounts with proper HTTP fallback for serverless environment"""
    load_logs = []
    load_logs.append("[LOAD] Starting account load process...")
    
    # Check local file first (though it won't exist in serverless)
    try:
        accounts_file = '/tmp/kingmailer_accounts.json'
        if os.path.exists(accounts_file):
            with open(accounts_file, 'r') as f:
                data = json.load(f)
                smtp_count = len(data.get('smtp_accounts', []))
                if smtp_count > 0:
                    load_logs.append(f"[LOAD] SUCCESS Local file: SMTP: {smtp_count}")
                    data['_load_logs'] = load_logs
                    return data
        load_logs.append("[LOAD] No local file found - using HTTP fallback")
    except Exception as e:
        load_logs.append(f"[LOAD] Local file error: {e}")
    
    # HTTP fallback - make direct request to accounts API
    try:
        import urllib.request
        import ssl
        
        # Create SSL context that accepts all certificates
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Use absolute URL
        accounts_url = 'https://kingmailer-vercel.vercel.app/api/accounts'
        load_logs.append(f"[LOAD] HTTP request to: {accounts_url}")
        
        req = urllib.request.Request(accounts_url)
        req.add_header('User-Agent', 'Mozilla/5.0 (KingMailer AccountStats)')
        req.add_header('Accept', 'application/json')
        
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            response_text = response.read().decode('utf-8')
            load_logs.append(f"[LOAD] HTTP response length: {len(response_text)}")
            
            data = json.loads(response_text)
            if data.get('success'):
                accounts_data = data.get('accounts', {})
                smtp_count = len(accounts_data.get('smtp_accounts', []))
                ses_count = len(accounts_data.get('ses_accounts', []))
                gmail_count = len(accounts_data.get('gmail_api_accounts', []))
                
                load_logs.append(f"[LOAD] HTTP SUCCESS: SMTP: {smtp_count}, SES: {ses_count}, Gmail: {gmail_count}")
                
                if smtp_count > 0 or ses_count > 0 or gmail_count > 0:
                    load_logs.append(f"[LOAD] Found {smtp_count + ses_count + gmail_count} real accounts!")
                    accounts_data['_load_logs'] = load_logs
                    return accounts_data
                else:
                    load_logs.append("[LOAD] No real accounts found via HTTP")
            else:
                load_logs.append(f"[LOAD] HTTP response error: {data.get('error', 'Unknown')}")
                
    except urllib.error.HTTPError as he:
        load_logs.append(f"[LOAD] HTTP Error {he.code}: {he.reason}")
    except Exception as e:
        load_logs.append(f"[LOAD] HTTP Exception: {e}")
    
    # Return empty as last resort
    load_logs.append("[LOAD] Returning empty accounts (no real accounts found)")
    return {
        'smtp_accounts': [],
        'ses_accounts': [],
        'gmail_api_accounts': [],
        'ec2_relays': [],
        '_load_logs': load_logs
    }

def load_account_tracking_stats():
    """Load account tracking statistics"""
    try:
        stats_file = '/tmp/kingmailer_account_stats.json'
        if os.path.exists(stats_file):
            with open(stats_file, 'r') as f:
                data = json.load(f)
                print(f"[ACCOUNT-STATS] SUCCESS Loaded tracking stats: SMTP: {len(data.get('smtp', {}))}, SES: {len(data.get('ses', {}))}, Gmail API: {len(data.get('gmail_api', {}))}")
                return data
    except Exception as e:
        print(f"[ACCOUNT-STATS] WARNING Error loading tracking stats: {e}")
    return {"smtp": {}, "gmail_api": {}, "ses": {}}

def merge_accounts_with_stats():
    """Merge saved accounts with their tracking statistics - FIXED VERSION"""
    saved_accounts = load_saved_accounts()
    tracking_stats = load_account_tracking_stats()
    
    # Add debug info to response
    debug_logs = []
    debug_logs.append("[MERGE] Starting merge process")
    debug_logs.append(f"[MERGE] Saved accounts: SMTP: {len(saved_accounts.get('smtp_accounts', []))}, SES: {len(saved_accounts.get('ses_accounts', []))}, Gmail: {len(saved_accounts.get('gmail_api_accounts', []))}")
    
    comprehensive_stats = {
        'smtp': {},
        'gmail_api': {},  
        'ses': {},
        'ec2': {}
    }
    
    has_real_accounts = False
    total_processed = 0
    
    # Process SMTP accounts
    smtp_accounts = saved_accounts.get('smtp_accounts', [])
    debug_logs.append(f"[MERGE] Processing {len(smtp_accounts)} SMTP accounts")
    
    for account in smtp_accounts:
        has_real_accounts = True
        total_processed += 1
        account_id = account.get('user', 'unknown')
        stats = tracking_stats.get('smtp', {}).get(account_id, {})
        
        debug_logs.append(f"[MERGE] SMTP account: {account_id}")
        
        comprehensive_stats['smtp'][account_id] = {
            'account_id': account_id,
            'account_type': 'smtp',
            'label': account.get('label', f'SMTP Account - {account_id}'),
            'provider': account.get('provider', 'gmail'),
            'created_at': account.get('created_at', datetime.now().isoformat()),
            'emails_sent': stats.get('emails_sent', 0),
            'failed_attempts': stats.get('failed_attempts', 0),
            'total_failures': stats.get('total_failures', 0),
            'is_active': stats.get('is_active', True),
            'last_failure': stats.get('last_failure'),
            'has_stats': bool(stats),
            'is_placeholder': False,
            'is_real_account': True
        }
    
    # Process Gmail API accounts
    gmail_accounts = saved_accounts.get('gmail_api_accounts', [])
    debug_logs.append(f"[MERGE] Processing {len(gmail_accounts)} Gmail API accounts")
    
    for account in gmail_accounts:
        has_real_accounts = True
        total_processed += 1
        account_id = account.get('user', 'unknown')
        stats = tracking_stats.get('gmail_api', {}).get(account_id, {})
        
        debug_logs.append(f"[MERGE] Gmail API account: {account_id}")
        
        comprehensive_stats['gmail_api'][account_id] = {
            'account_id': account_id,
            'account_type': 'gmail_api',
            'label': account.get('label', f'Gmail API Account - {account_id}'),
            'created_at': account.get('created_at', datetime.now().isoformat()),
            'emails_sent': stats.get('emails_sent', 0),
            'failed_attempts': stats.get('failed_attempts', 0),
            'total_failures': stats.get('total_failures', 0),
            'is_active': stats.get('is_active', True),
            'last_failure': stats.get('last_failure'),
            'has_stats': bool(stats),
            'is_placeholder': False,
            'is_real_account': True
        }
    
    # Process SES accounts
    ses_accounts = saved_accounts.get('ses_accounts', [])
    debug_logs.append(f"[MERGE] Processing {len(ses_accounts)} SES accounts")
    
    for account in ses_accounts:
        has_real_accounts = True
        total_processed += 1
        region = account.get('region', 'unknown')
        access_key = account.get('access_key_id', account.get('access_key', 'unknown'))
        account_id = f"{region}_{access_key[:8]}"
        stats = tracking_stats.get('ses', {}).get(account_id, {})
        
        debug_logs.append(f"[MERGE] SES account: {account_id}")
        
        comprehensive_stats['ses'][account_id] = {
            'account_id': account_id,
            'account_type': 'ses',
            'label': account.get('label', f'SES Account - {region}'),
            'region': region,
            'from_email': account.get('from_email', ''),
            'created_at': account.get('created_at', datetime.now().isoformat()),
            'emails_sent': stats.get('emails_sent', 0),
            'failed_attempts': stats.get('failed_attempts', 0),
            'total_failures': stats.get('total_failures', 0),
            'is_active': stats.get('is_active', True),
            'last_failure': stats.get('last_failure'),
            'has_stats': bool(stats),
            'is_placeholder': False,
            'is_real_account': True
        }
    
    debug_logs.append(f"[MERGE] Total accounts processed: {total_processed}")
    debug_logs.append(f"[MERGE] Has real accounts: {has_real_accounts}")
    
    # If no real accounts, show demo accounts
    if not has_real_accounts:
        debug_logs.append("[MERGE] No real accounts found, showing demo accounts")
        comprehensive_stats['smtp']['demo_smtp_user@gmail.com'] = {
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
    else:
        debug_logs.append(f"[MERGE] Returning {total_processed} real accounts")
    
    # Attach debug info to the result
    comprehensive_stats['_debug_logs'] = debug_logs
    
    return comprehensive_stats

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Get comprehensive account statistics"""
        try:
            account_stats = merge_accounts_with_stats()
            
            # Extract debug logs before calculating summaries
            load_logs = account_stats.pop('_load_logs', [])
            debug_logs = account_stats.pop('_debug_logs', [])
            
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
            real_accounts = sum(
                sum(1 for acc in accounts.values() if acc.get('is_real_account', False)) 
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
                    "real_accounts": real_accounts,
                    "account_breakdown": {
                        "smtp": len(account_stats['smtp']),
                        "gmail_api": len(account_stats['gmail_api']),
                        "ses": len(account_stats['ses']),
                        "ec2": len(account_stats['ec2'])
                    }
                },
                "debug": {
                    "serverless_note": "Serverless function with HTTP fallback", 
                    "turbo_mode_enabled": True,
                    "account_deactivation_enabled": True,
                    "tracking_system_active": True,
                    "load_logs": account_stats.get('_load_logs', []),
                    "debug_logs": account_stats.get('_debug_logs', [])
                }
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
            
            response_json = json.dumps(response_data, indent=2)
            self.wfile.write(response_json.encode())
            
            print(f"[ACCOUNT-STATS] SUCCESS Returned {total_accounts} accounts ({real_accounts} real, {placeholder_accounts} placeholder)")
            
        except Exception as e:
            print(f"[ACCOUNT-STATS] ERROR: {str(e)}")
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