"""
KINGMAILER v4.1 - Account Management API
Vercel Serverless Function for managing SMTP/SES/EC2 accounts
Accounts are isolated per logged-in user and per device (HWID).
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime

ACCOUNTS_FILE = '/tmp/kingmailer_accounts.json'
ACCOUNT_TYPES = {
    'smtp': 'smtp_accounts',
    'ses': 'ses_accounts',
    'gmail_api': 'gmail_api_accounts',
    'ec2': 'ec2_relays',
}
EMPTY_ACCOUNTS = {
    'smtp_accounts': [],
    'ses_accounts': [],
    'gmail_api_accounts': [],
    'ec2_relays': [],
}


def _empty_accounts():
    return {
        'smtp_accounts': [],
        'ses_accounts': [],
        'gmail_api_accounts': [],
        'ec2_relays': [],
    }


def _normalize_storage(raw):
    if isinstance(raw, dict) and 'scopes' in raw and isinstance(raw['scopes'], dict):
        return raw

    legacy_accounts = raw if isinstance(raw, dict) else {}
    if any(key in legacy_accounts for key in EMPTY_ACCOUNTS):
        return {
            'version': 2,
            'scopes': {
                '__legacy_global__': {
                    'username': '__legacy_global__',
                    'hwid': '__legacy_global__',
                    'accounts': {
                        'smtp_accounts': list(legacy_accounts.get('smtp_accounts', [])),
                        'ses_accounts': list(legacy_accounts.get('ses_accounts', [])),
                        'gmail_api_accounts': list(legacy_accounts.get('gmail_api_accounts', [])),
                        'ec2_relays': list(legacy_accounts.get('ec2_relays', [])),
                    }
                }
            }
        }

    return {'version': 2, 'scopes': {}}


def load_storage():
    try:
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                return _normalize_storage(json.load(f))
    except Exception as exc:
        print(f"[ACCOUNTS] ERROR Failed to load storage: {exc}")
    return {'version': 2, 'scopes': {}}


def save_storage(storage):
    try:
        os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(storage, f, indent=2)
        total_scopes = len(storage.get('scopes', {}))
        print(f"[ACCOUNTS] SUCCESS Saved scoped account storage for {total_scopes} scope(s)")
        return True
    except Exception as exc:
        print(f"[ACCOUNTS] ERROR Failed to save storage: {exc}")
        return False


def get_scope_context(handler, body_data=None):
    username = (
        handler.headers.get('X-Kingmailer-User')
        or handler.headers.get('X-Username')
        or (body_data or {}).get('username')
        or ''
    ).strip().lower()
    hwid = (
        handler.headers.get('X-Kingmailer-Hwid')
        or handler.headers.get('X-Hwid')
        or (body_data or {}).get('hwid')
        or ''
    ).strip()
    if not username or not hwid:
        return None, username, hwid
    return f"{username}::{hwid}", username, hwid


def get_scope_accounts(storage, scope_key, username='', hwid=''):
    scopes = storage.setdefault('scopes', {})
    if scope_key not in scopes:
        scopes[scope_key] = {
            'username': username,
            'hwid': hwid,
            'accounts': _empty_accounts(),
        }
    scope = scopes[scope_key]
    scope.setdefault('username', username)
    scope.setdefault('hwid', hwid)
    scope.setdefault('accounts', _empty_accounts())
    for key in EMPTY_ACCOUNTS:
        scope['accounts'].setdefault(key, [])
    return scope['accounts']


def send_json(handler, status_code, payload):
    handler.send_response(status_code)
    handler.send_header('Content-type', 'application/json')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Kingmailer-User, X-Kingmailer-Hwid, X-Username, X-Hwid')
    handler.end_headers()
    handler.wfile.write(json.dumps(payload).encode())


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            storage = load_storage()
            scope_key, username, hwid = get_scope_context(self)
            if not scope_key:
                return send_json(self, 401, {'success': False, 'error': 'username and hwid are required'})

            accounts = get_scope_accounts(storage, scope_key, username=username, hwid=hwid)
            return send_json(self, 200, {
                'success': True,
                'accounts': accounts,
                'scope': {'username': username, 'hwid': hwid}
            })
        except Exception as exc:
            return send_json(self, 500, {'success': False, 'error': str(exc)})

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', '0'))
            post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
            data = json.loads(post_data.decode('utf-8'))

            storage = load_storage()
            scope_key, username, hwid = get_scope_context(self, data)
            if not scope_key:
                return send_json(self, 401, {'success': False, 'error': 'username and hwid are required'})

            accounts = get_scope_accounts(storage, scope_key, username=username, hwid=hwid)
            account_type = data.get('type')
            target_key = ACCOUNT_TYPES.get(account_type)
            if not target_key:
                return send_json(self, 400, {'success': False, 'error': 'Invalid account type'})

            next_id = max([acc.get('id', 0) for acc in accounts[target_key]] + [0]) + 1

            if account_type == 'smtp':
                account = {
                    'id': next_id,
                    'provider': data.get('provider', 'gmail'),
                    'user': data.get('user'),
                    'pass': data.get('pass'),
                    'host': data.get('host'),
                    'port': data.get('port', 587),
                    'sender_name': data.get('sender_name', ''),
                    'label': data.get('label', f"SMTP Account #{next_id}"),
                    'created_at': datetime.now().isoformat()
                }
                accounts[target_key].append(account)
                save_storage(storage)
                return send_json(self, 200, {'success': True, 'message': 'SMTP account added successfully', 'account': account})

            if account_type == 'ses':
                account = {
                    'id': next_id,
                    'access_key_id': data.get('access_key'),
                    'secret_access_key': data.get('secret_key'),
                    'region': data.get('region', 'us-east-1'),
                    'from_email': data.get('from_email'),
                    'label': data.get('label', f"SES Account #{next_id}"),
                    'created_at': datetime.now().isoformat()
                }
                accounts[target_key].append(account)
                save_storage(storage)
                return send_json(self, 200, {'success': True, 'message': 'AWS SES account added successfully', 'account': account})

            if account_type == 'gmail_api':
                account = {
                    'id': next_id,
                    'user': data.get('user'),
                    'client_id': data.get('client_id'),
                    'client_secret': data.get('client_secret'),
                    'refresh_token': data.get('refresh_token'),
                    'sender_name': data.get('sender_name', ''),
                    'label': data.get('label', f"Gmail API Account #{next_id}"),
                    'created_at': datetime.now().isoformat()
                }
                accounts[target_key].append(account)
                save_storage(storage)
                return send_json(self, 200, {'success': True, 'message': 'Gmail API account added successfully', 'account': account})

            relay = {
                'id': next_id,
                'url': data.get('url'),
                'instance_id': data.get('instance_id'),
                'public_ip': data.get('public_ip'),
                'label': data.get('label', f"EC2 Relay #{next_id}"),
                'created_at': datetime.now().isoformat()
            }
            accounts[target_key].append(relay)
            save_storage(storage)
            return send_json(self, 200, {'success': True, 'message': 'EC2 relay added successfully', 'relay': relay})
        except Exception as exc:
            return send_json(self, 500, {'success': False, 'error': str(exc)})

    def do_DELETE(self):
        try:
            content_length = int(self.headers.get('Content-Length', '0'))
            post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
            data = json.loads(post_data.decode('utf-8'))

            storage = load_storage()
            scope_key, username, hwid = get_scope_context(self, data)
            if not scope_key:
                return send_json(self, 401, {'success': False, 'error': 'username and hwid are required'})

            accounts = get_scope_accounts(storage, scope_key, username=username, hwid=hwid)
            account_type = data.get('type')
            account_id = data.get('id')
            target_key = ACCOUNT_TYPES.get(account_type)
            if not target_key:
                return send_json(self, 400, {'success': False, 'error': 'Invalid account type'})

            before_count = len(accounts[target_key])
            accounts[target_key] = [acc for acc in accounts[target_key] if acc.get('id') != account_id]
            save_storage(storage)

            return send_json(self, 200, {
                'success': True,
                'message': 'Account deleted successfully',
                'deleted': before_count != len(accounts[target_key])
            })
        except Exception as exc:
            return send_json(self, 500, {'success': False, 'error': str(exc)})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-Kingmailer-User, X-Kingmailer-Hwid, X-Username, X-Hwid')
        self.end_headers()
