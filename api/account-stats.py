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
    """Merge saved accounts with their tracking statistics and auto-remove deactivated accounts"""
    saved_accounts = load_saved_accounts()
    tracking_stats = load_account_tracking_stats()
    
    # Add debug info to response
    debug_logs = []
    debug_logs.append("[MERGE] Starting merge process with auto-cleanup")
    debug_logs.append(f"[MERGE] Saved accounts: SMTP: {len(saved_accounts.get('smtp_accounts', []))}, SES: {len(saved_accounts.get('ses_accounts', []))}, Gmail: {len(saved_accounts.get('gmail_api_accounts', []))}")
    
    comprehensive_stats = {
        'smtp': {},
        'gmail_api': {},  
        'ses': {},
        'ec2': {}
    }
    
    has_real_accounts = False
    total_processed = 0
    accounts_to_remove = []  # Track deactivated accounts for removal
    
    # Process SMTP accounts
    smtp_accounts = saved_accounts.get('smtp_accounts', [])
    debug_logs.append(f"[MERGE] Processing {len(smtp_accounts)} SMTP accounts")
    
    for account in smtp_accounts:
        has_real_accounts = True
        total_processed += 1
        account_id = account.get('user', 'unknown')
        stats = tracking_stats.get('smtp', {}).get(account_id, {})
        
        # Check if account is deactivated
        is_active = stats.get('is_active', True)
        if not is_active and stats.get('failed_attempts', 0) >= 3:
            debug_logs.append(f"[MERGE] ⚠️ SMTP account {account_id} is DEACTIVATED - marking for removal")
            accounts_to_remove.append(('smtp', account_id))
            # Don't add to comprehensive stats - effectively removing it
            continue
        
        debug_logs.append(f"[MERGE] ✓ SMTP account: {account_id} - {stats.get('emails_sent', 0)} emails sent")
        
        comprehensive_stats['smtp'][account_id] = {
            'account_id': account_id,
            'account_type': 'smtp',
            'label': account.get('label', f'SMTP Account - {account_id}'),
            'provider': account.get('provider', 'gmail'),
            'created_at': account.get('created_at', datetime.now().isoformat()),
            'emails_sent': stats.get('emails_sent', 0),
            'failed_attempts': stats.get('failed_attempts', 0),
            'total_failures': stats.get('total_failures', 0),
            'is_active': is_active,
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
        
        # Check if account is deactivated
        is_active = stats.get('is_active', True)
        if not is_active and stats.get('failed_attempts', 0) >= 3:
            debug_logs.append(f"[MERGE] ⚠️ Gmail API account {account_id} is DEACTIVATED - marking for removal")
            accounts_to_remove.append(('gmail_api', account_id))
            continue
        
        debug_logs.append(f"[MERGE] ✓ Gmail API account: {account_id} - {stats.get('emails_sent', 0)} emails sent")
        
        comprehensive_stats['gmail_api'][account_id] = {
            'account_id': account_id,
            'account_type': 'gmail_api',
            'label': account.get('label', f'Gmail API Account - {account_id}'),
            'created_at': account.get('created_at', datetime.now().isoformat()),
            'emails_sent': stats.get('emails_sent', 0),
            'failed_attempts': stats.get('failed_attempts', 0),
            'total_failures': stats.get('total_failures', 0),
            'is_active': is_active,
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
        
        # Check if account is deactivated
        is_active = stats.get('is_active', True)
        if not is_active and stats.get('failed_attempts', 0) >= 3:
            debug_logs.append(f"[MERGE] ⚠️ SES account {account_id} is DEACTIVATED - marking for removal")
            accounts_to_remove.append(('ses', account_id))
            continue
        
        debug_logs.append(f"[MERGE] ✓ SES account: {account_id} - {stats.get('emails_sent', 0)} emails sent")
        
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
            'is_active': is_active,
            'last_failure': stats.get('last_failure'),
            'has_stats': bool(stats),
            'is_placeholder': False,
            'is_real_account': True
        }
    
    # Auto-remove deactivated accounts from saved list
    if accounts_to_remove:
        debug_logs.append(f"[CLEANUP] Auto-removing {len(accounts_to_remove)} deactivated accounts from saved list")
        remove_deactivated_accounts_from_saved(saved_accounts, accounts_to_remove, debug_logs)
    
    debug_logs.append(f"[MERGE] Total accounts processed: {total_processed}")
    debug_logs.append(f"[MERGE] Active accounts: {total_processed - len(accounts_to_remove)}")
    debug_logs.append(f"[MERGE] Removed accounts: {len(accounts_to_remove)}")
    
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
    
    # Attach debug info to the result
    comprehensive_stats['_debug_logs'] = debug_logs
    comprehensive_stats['_accounts_removed'] = len(accounts_to_remove)
    
    return comprehensive_stats

def remove_deactivated_accounts_from_saved(saved_accounts, accounts_to_remove, debug_logs):
    """Remove deactivated accounts from the saved accounts file"""
    try:
        accounts_file = '/tmp/kingmailer_accounts.json'
        
        # Group removals by type
        removal_map = {}
        for account_type, account_id in accounts_to_remove:
            if account_type not in removal_map:
                removal_map[account_type] = []
            removal_map[account_type].append(account_id)
        
        # Remove SMTP accounts
        if 'smtp' in removal_map:
            smtp_accounts = saved_accounts.get('smtp_accounts', [])
            original_count = len(smtp_accounts)
            smtp_accounts = [acc for acc in smtp_accounts if acc.get('user') not in removal_map['smtp']]
            saved_accounts['smtp_accounts'] = smtp_accounts
            debug_logs.append(f"[CLEANUP] Removed {original_count - len(smtp_accounts)} SMTP accounts")
        
        # Remove Gmail API accounts
        if 'gmail_api' in removal_map:
            gmail_accounts = saved_accounts.get('gmail_api_accounts', [])
            original_count = len(gmail_accounts)
            gmail_accounts = [acc for acc in gmail_accounts if acc.get('user') not in removal_map['gmail_api']]
            saved_accounts['gmail_api_accounts'] = gmail_accounts
            debug_logs.append(f"[CLEANUP] Removed {original_count - len(gmail_accounts)} Gmail API accounts")
        
        # Remove SES accounts (more complex ID matching)
        if 'ses' in removal_map:
            ses_accounts = saved_accounts.get('ses_accounts', [])
            original_count = len(ses_accounts)
            filtered_ses = []
            for acc in ses_accounts:
                region = acc.get('region', 'unknown')
                access_key = acc.get('access_key_id', acc.get('access_key', 'unknown'))
                account_id = f"{region}_{access_key[:8]}"
                if account_id not in removal_map['ses']:
                    filtered_ses.append(acc)
            saved_accounts['ses_accounts'] = filtered_ses
            debug_logs.append(f"[CLEANUP] Removed {original_count - len(filtered_ses)} SES accounts")
        
        # Save updated accounts file
        if os.path.exists(accounts_file) or True:  # Always try to save
            os.makedirs(os.path.dirname(accounts_file), exist_ok=True)
            with open(accounts_file, 'w') as f:
                json.dump(saved_accounts, f, indent=2)
            debug_logs.append(f"[CLEANUP] ✓ Successfully saved updated accounts file")
            print(f"[ACCOUNT-STATS] Removed {len(accounts_to_remove)} deactivated accounts from saved list")
        
    except Exception as e:
        debug_logs.append(f"[CLEANUP] ✗ Error removing accounts: {e}")
        print(f"[ACCOUNT-STATS] ERROR removing deactivated accounts: {e}")

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Get comprehensive account statistics"""
        try:
            account_stats = merge_accounts_with_stats()
            
            # Extract debug logs and metadata BEFORE calculating summaries
            load_logs = account_stats.pop('_load_logs', [])
            debug_logs = account_stats.pop('_debug_logs', [])
            accounts_removed = account_stats.pop('_accounts_removed', 0)
            
            # Calculate summaries (only iterate over actual account types, not metadata)
            account_types = ['smtp', 'gmail_api', 'ses', 'ec2']
            
            total_accounts = sum(len(account_stats.get(acc_type, {})) for acc_type in account_types)
            total_emails_sent = sum(
                sum(acc.get('emails_sent', 0) for acc in account_stats.get(acc_type, {}).values()) 
                for acc_type in account_types
            )
            active_accounts = sum(
                sum(1 for acc in account_stats.get(acc_type, {}).values() if acc.get('is_active', True)) 
                for acc_type in account_types
            )
            deactivated_accounts = sum(
                sum(1 for acc in account_stats.get(acc_type, {}).values() if not acc.get('is_active', True)) 
                for acc_type in account_types
            )
            accounts_with_stats = sum(
                sum(1 for acc in account_stats.get(acc_type, {}).values() if acc.get('has_stats', False)) 
                for acc_type in account_types
            )
            placeholder_accounts = sum(
                sum(1 for acc in account_stats.get(acc_type, {}).values() if acc.get('is_placeholder', False)) 
                for acc_type in account_types
            )
            real_accounts = sum(
                sum(1 for acc in account_stats.get(acc_type, {}).values() if acc.get('is_real_account', False)) 
                for acc_type in account_types
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
                    "accounts_removed_this_check": accounts_removed,
                    "account_breakdown": {
                        "smtp": len(account_stats.get('smtp', {})),
                        "gmail_api": len(account_stats.get('gmail_api', {})),
                        "ses": len(account_stats.get('ses', {})),
                        "ec2": len(account_stats.get('ec2', {}))
                    }
                },
                "debug": {
                    "serverless_note": "Serverless function with HTTP fallback and auto-cleanup", 
                    "turbo_mode_enabled": True,
                    "account_deactivation_enabled": True,
                    "auto_removal_enabled": True,
                    "tracking_system_active": True,
                    "load_logs": load_logs,
                    "debug_logs": debug_logs
                },
                "features": {
                    "auto_cleanup": "Deactivated accounts are automatically removed from saved list",
                    "email_tracking": "Each account shows total emails sent and failure count",
                    "batch_protection": "Deactivated accounts won't be used in same batch"
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