"""
KINGMAILER v4.0 - Account Management API  
Vercel Serverless Function for managing SMTP/SES accounts
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime

# File-based persistent storage
ACCOUNTS_FILE = '/tmp/kingmailer_accounts.json'

def load_accounts():
    """Load accounts from persistent file storage"""
    try:
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {
        'smtp_accounts': [],
        'ses_accounts': [],
        'gmail_api_accounts': [],
        'ec2_relays': []
    }

def save_accounts(accounts):
    """Save accounts to persistent file storage - Enhanced with debugging"""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
        
        with open(ACCOUNTS_FILE, 'w') as f:
            json.dump(accounts, f, indent=2)
        
        print(f"[ACCOUNTS] SUCCESS Saved accounts: SMTP: {len(accounts.get('smtp_accounts', []))}, SES: {len(accounts.get('ses_accounts', []))}, Gmail API: {len(accounts.get('gmail_api_accounts', []))}, EC2: {len(accounts.get('ec2_relays', []))}")
        return True
    except Exception as e:
        print(f"[ACCOUNTS] ERROR Failed to save accounts: {e}")
        return False


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Return all accounts"""
        try:
            accounts = load_accounts()
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                'success': True,
                'accounts': accounts
            }
            
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
    
    def do_POST(self):
        """Add new account"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            accounts = load_accounts()
            account_type = data.get('type')  # 'smtp', 'ses', 'gmail_api', 'ec2'
            
            if account_type == 'smtp':
                account = {
                    'id': len(accounts['smtp_accounts']) + 1,
                    'provider': data.get('provider', 'gmail'),
                    'user': data.get('user'),
                    'pass': data.get('pass'),
                    'host': data.get('host'),
                    'port': data.get('port', 587),
                    'sender_name': data.get('sender_name', ''),
                    'label': data.get('label', f"SMTP Account #{len(accounts['smtp_accounts']) + 1}"),
                    'created_at': datetime.now().isoformat()
                }
                accounts['smtp_accounts'].append(account)
                save_accounts(accounts)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'message': 'SMTP account added successfully',
                    'account': account
                }).encode())
            
            elif account_type == 'ses':
                account = {
                    'id': len(accounts['ses_accounts']) + 1,
                    'access_key_id': data.get('access_key'),
                    'secret_access_key': data.get('secret_key'),
                    'region': data.get('region', 'us-east-1'),
                    'from_email': data.get('from_email'),
                    'label': data.get('label', f"SES Account #{len(accounts['ses_accounts']) + 1}"),
                    'created_at': datetime.now().isoformat()
                }
                accounts['ses_accounts'].append(account)
                save_accounts(accounts)
                
            elif account_type == 'gmail_api':
                account = {
                    'id': len(accounts['gmail_api_accounts']) + 1,
                    'user': data.get('user'),
                    'client_id': data.get('client_id'),
                    'client_secret': data.get('client_secret'),
                    'refresh_token': data.get('refresh_token'),
                    'sender_name': data.get('sender_name', ''),
                    'label': data.get('label', f"Gmail API Account #{len(accounts['gmail_api_accounts']) + 1}"),
                    'created_at': datetime.now().isoformat()
                }
                accounts['gmail_api_accounts'].append(account)
                save_accounts(accounts)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'message': 'AWS SES account added successfully',
                    'account': account
                }).encode())
            
            elif account_type == 'ec2':
                relay = {
                    'id': len(accounts['ec2_relays']) + 1,
                    'url': data.get('url'),
                    'instance_id': data.get('instance_id'),
                    'public_ip': data.get('public_ip'),
                    'label': data.get('label', f"EC2 Relay #{len(accounts['ec2_relays']) + 1}"),
                    'created_at': datetime.now().isoformat()
                }
                accounts['ec2_relays'].append(relay)
                save_accounts(accounts)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'message': 'EC2 relay added successfully',
                    'relay': relay
                }).encode())
            
            else:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Invalid account type'}).encode())
        
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
    
    def do_DELETE(self):
        """Delete account"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            account_type = data.get('type')
            account_id = data.get('id')
            
            if account_type == 'smtp':
                ACCOUNTS_STORE['smtp_accounts'] = [
                    acc for acc in ACCOUNTS_STORE['smtp_accounts'] 
                    if acc['id'] != account_id
                ]
            elif account_type == 'ses':
                ACCOUNTS_STORE['ses_accounts'] = [
                    acc for acc in ACCOUNTS_STORE['ses_accounts'] 
                    if acc['id'] != account_id
                ]
            elif account_type == 'ec2':
                ACCOUNTS_STORE['ec2_relays'] = [
                    relay for relay in ACCOUNTS_STORE['ec2_relays'] 
                    if relay['id'] != account_id
                ]
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'message': 'Account deleted successfully'
            }).encode())
        
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
