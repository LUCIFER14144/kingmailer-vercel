"""
KINGMAILER v4.0 - Account Management API  
Vercel Serverless Function for managing SMTP/SES accounts
"""

from http.server import BaseHTTPRequestHandler
import json

# In-memory storage (for demo - use database in production)
ACCOUNTS_STORE = {
    'smtp_accounts': [],
    'ses_accounts': [],
    'ec2_relays': []
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Return all accounts"""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                'success': True,
                'accounts': ACCOUNTS_STORE
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
            
            account_type = data.get('type')  # 'smtp', 'ses', 'ec2'
            
            if account_type == 'smtp':
                account = {
                    'id': len(ACCOUNTS_STORE['smtp_accounts']) + 1,
                    'provider': data.get('provider', 'gmail'),
                    'user': data.get('user'),
                    'pass': data.get('pass'),
                    'host': data.get('host'),
                    'port': data.get('port', 587),
                    'label': data.get('label', f"SMTP Account #{len(ACCOUNTS_STORE['smtp_accounts']) + 1}")
                }
                ACCOUNTS_STORE['smtp_accounts'].append(account)
                
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
                    'id': len(ACCOUNTS_STORE['ses_accounts']) + 1,
                    'access_key': data.get('access_key'),
                    'secret_key': data.get('secret_key'),
                    'region': data.get('region', 'us-east-1'),
                    'from_email': data.get('from_email'),
                    'label': data.get('label', f"SES Account #{len(ACCOUNTS_STORE['ses_accounts']) + 1}")
                }
                ACCOUNTS_STORE['ses_accounts'].append(account)
                
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
                    'id': len(ACCOUNTS_STORE['ec2_relays']) + 1,
                    'url': data.get('url'),
                    'label': data.get('label', f"EC2 Relay #{len(ACCOUNTS_STORE['ec2_relays']) + 1}")
                }
                ACCOUNTS_STORE['ec2_relays'].append(relay)
                
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
