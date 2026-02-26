"""
KINGMAILER v4.0 - User Management API
Create, read, delete users (Admin only)
"""

from http.server import BaseHTTPRequestHandler
import json
import hashlib
from datetime import datetime

# In-memory user database
# In production, use a real database (MongoDB, PostgreSQL, etc.)
USERS_DB = {
    'admin': {
        'password': hashlib.sha256('admin123'.encode()).hexdigest(),
        'role': 'admin',
        'created_at': '2026-02-25 00:00:00'
    },
    'demo': {
        'password': hashlib.sha256('demo'.encode()).hexdigest(),
        'role': 'user',
        'created_at': '2026-02-25 00:00:00'
    },
    'user': {
        'password': hashlib.sha256('password'.encode()).hexdigest(),
        'role': 'user',
        'created_at': '2026-02-25 00:00:00'
    }
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Get all users or stats"""
        try:
            # Parse path
            path = self.path.split('?')[0]
            
            if path == '/api/users/stats':
                # Return statistics
                total = len(USERS_DB)
                admins = sum(1 for u in USERS_DB.values() if u.get('role') == 'admin')
                users = total - admins
                
                result = {
                    'success': True,
                    'stats': {
                        'total_users': total,
                        'admin_users': admins,
                        'regular_users': users
                    }
                }
            else:
                # Return all users (without passwords)
                users_list = []
                for username, data in USERS_DB.items():
                    users_list.append({
                        'username': username,
                        'role': data.get('role', 'user'),
                        'created_at': data.get('created_at', 'N/A')
                    })
                
                result = {
                    'success': True,
                    'users': users_list,
                    'count': len(users_list)
                }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
    
    def do_POST(self):
        """Create new user"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            role = data.get('role', 'user')
            
            # Validation
            if not username or not password:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Username and password required'
                }).encode())
                return
            
            if len(password) < 6:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Password must be at least 6 characters'
                }).encode())
                return
            
            # Check if user already exists
            if username in USERS_DB:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': f'User "{username}" already exists'
                }).encode())
                return
            
            # Create user
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            USERS_DB[username] = {
                'password': password_hash,
                'role': role,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            result = {
                'success': True,
                'message': f'User "{username}" created successfully',
                'user': {
                    'username': username,
                    'role': role
                }
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
    
    def do_DELETE(self):
        """Delete user"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            username = data.get('username', '').strip()
            
            if not username:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Username required'
                }).encode())
                return
            
            # Protect admin account
            if username == 'admin':
                self.send_response(403)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Cannot delete admin account'
                }).encode())
                return
            
            # Delete user
            if username in USERS_DB:
                del USERS_DB[username]
                
                result = {
                    'success': True,
                    'message': f'User "{username}" deleted successfully'
                }
            else:
                result = {
                    'success': False,
                    'error': f'User "{username}" not found'
                }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        
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
