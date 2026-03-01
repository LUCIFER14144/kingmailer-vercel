"""
KINGMAILER v4.0 - Unified Auth & User Management API
Deployed to Vercel. We use a single serverless function to share state.
"""

from http.server import BaseHTTPRequestHandler
import json
import hashlib
import os
from datetime import datetime

DB_PATH = "/tmp/users.json"

DEFAULT_DB = {
    "last_reset_date": datetime.now().strftime('%Y-%m-%d'),
    "users": {
        "admin": {
            "password": hashlib.sha256('admin123'.encode()).hexdigest(),
            "role": "admin",
            "created_at": "2026-02-25 00:00:00",
            "max_devices": 1,
            "active_hwids": []
        },
        "demo": {
            "password": hashlib.sha256('demo'.encode()).hexdigest(),
            "role": "user",
            "created_at": "2026-02-25 00:00:00",
            "max_devices": 1,
            "active_hwids": []
        },
        "user": {
            "password": hashlib.sha256('password'.encode()).hexdigest(),
            "role": "user",
            "created_at": "2026-02-25 00:00:00",
            "max_devices": 1,
            "active_hwids": []
        }
    }
}

def load_db():
    if not os.path.exists(DB_PATH):
        save_db(DEFAULT_DB)
        return DEFAULT_DB
    
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Daily auto-reset HWIDs logic
        today_str = datetime.now().strftime('%Y-%m-%d')
        last_reset = data.get("last_reset_date", today_str)
        
        if last_reset != today_str:
            # It's a new day, clear all HWIDs!
            data["last_reset_date"] = today_str
            for u in data.get("users", {}).values():
                u["active_hwids"] = []
            save_db(data)
            
        return data
    except Exception:
        return DEFAULT_DB

def save_db(data):
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            path = self.path.split('?')[0]
            db = load_db()
            users_db = db["users"]
            
            if path == '/api/users/stats':
                total = len(users_db)
                admins = sum(1 for u in users_db.values() if u.get('role') == 'admin')
                users = total - admins
                
                result = {
                    'success': True,
                    'stats': {
                        'total_users': total,
                        'admin_users': admins,
                        'regular_users': users
                    }
                }
            elif path.startswith('/api/users'):
                # Return users with device usage stats
                users_list = []
                for username, udata in users_db.items():
                    users_list.append({
                        'username': username,
                        'role': udata.get('role', 'user'),
                        'created_at': udata.get('created_at', 'N/A'),
                        'max_devices': udata.get('max_devices', 1),
                        'active_devices': len(udata.get('active_hwids', []))
                    })
                
                result = {
                    'success': True,
                    'users': users_list,
                    'count': len(users_list)
                }
            else:
                self.send_error(404, "Not Found")
                return
            
            self._send_response(200, result)
        except Exception as e:
            self._send_response(500, {'success': False, 'error': str(e)})

    def do_POST(self):
        try:
            path = self.path.split('?')[0]
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            db = load_db()
            users_db = db["users"]
            
            if path == '/api/users':
                # Create user
                username = data.get('username', '').strip()
                password = data.get('password', '').strip()
                role = data.get('role', 'user')
                max_devices = int(data.get('max_devices', 1))
                
                if not username or not password:
                    return self._send_response(400, {'success': False, 'error': 'Username and password required'})
                
                if len(password) < 6:
                    return self._send_response(400, {'success': False, 'error': 'Password must be at least 6 characters'})
                
                if username in users_db:
                    return self._send_response(400, {'success': False, 'error': f'User "{username}" already exists'})
                
                users_db[username] = {
                    'password': hashlib.sha256(password.encode()).hexdigest(),
                    'role': role,
                    'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'max_devices': max_devices,
                    'active_hwids': []
                }
                save_db(db)
                
                return self._send_response(200, {
                    'success': True,
                    'message': f'User "{username}" created successfully',
                    'user': {'username': username, 'role': role, 'max_devices': max_devices}
                })

            elif path == '/api/users/reset_hwids':
                # Admin manual reset for a specific user
                username = data.get('username', '').strip()
                if username in users_db:
                    users_db[username]['active_hwids'] = []
                    save_db(db)
                    return self._send_response(200, {'success': True, 'message': f'HWIDs reset for {username}'})
                return self._send_response(404, {'success': False, 'error': 'User not found'})
            
            elif path == '/api/login':
                username = data.get('username', '').strip()
                password = data.get('password', '').strip()
                hwid = data.get('hwid', '').strip()
                
                if not username or not password:
                    return self._send_response(400, {'success': False, 'error': 'Username and password required'})
                    
                if not hwid:
                    # Fallback for old clients, give them a random one or strict error.
                    return self._send_response(400, {'success': False, 'error': 'HWID required for login from this client.'})
                
                password_hash = hashlib.sha256(password.encode()).hexdigest()
                user = users_db.get(username)
                
                if user and user['password'] == password_hash:
                    # Check HWID logic
                    active = user.setdefault('active_hwids', [])
                    max_dev = user.setdefault('max_devices', 1)
                    
                    if hwid not in active:
                        if len(active) >= max_dev:
                            return self._send_response(401, {'success': False, 'error': f'Device limit reached. Max {max_dev} allowed.'})
                        # Slot available
                        active.append(hwid)
                        save_db(db)
                        
                    token = hashlib.sha256(f"{username}:kingmailer".encode()).hexdigest()
                    return self._send_response(200, {
                        'success': True,
                        'message': 'Login successful',
                        'token': token,
                        'user': username
                    })
                
                return self._send_response(401, {'success': False, 'error': 'Invalid username or password'})
            
            elif path == '/api/logout':
                username = data.get('username', '').strip()
                hwid = data.get('hwid', '').strip()
                
                user = users_db.get(username)
                if user and hwid in user.setdefault('active_hwids', []):
                    user['active_hwids'].remove(hwid)
                    save_db(db)
                
                return self._send_response(200, {'success': True, 'message': 'Logged out successfully on server'})
                
        except Exception as e:
            self._send_response(500, {'success': False, 'error': str(e)})

    def do_DELETE(self):
        try:
            path = self.path.split('?')[0]
            if path.startswith('/api/users'):
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(body)
                
                username = data.get('username', '').strip()
                if not username:
                    return self._send_response(400, {'success': False, 'error': 'Username required'})
                
                if username == 'admin':
                    return self._send_response(403, {'success': False, 'error': 'Cannot delete admin account'})
                
                db = load_db()
                if username in db["users"]:
                    del db["users"][username]
                    save_db(db)
                    return self._send_response(200, {'success': True, 'message': f'User "{username}" deleted successfully'})
                
                return self._send_response(404, {'success': False, 'error': f'User "{username}" not found'})
                
        except Exception as e:
            self._send_response(500, {'success': False, 'error': str(e)})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
    def _send_response(self, status, payload):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())
