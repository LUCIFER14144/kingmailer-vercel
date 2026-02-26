"""
KINGMAILER v4.0 - Login API
Simple authentication endpoint
"""

from http.server import BaseHTTPRequestHandler
import json
import hashlib

# Simple user database (in production, use a real database)
USERS = {
    'admin': hashlib.sha256('admin123'.encode()).hexdigest(),
    'user': hashlib.sha256('password'.encode()).hexdigest(),
    'demo': hashlib.sha256('demo'.encode()).hexdigest()
}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            
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
            
            # Hash the provided password
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            # Check credentials
            if username in USERS and USERS[username] == password_hash:
                # Generate simple token (in production, use JWT)
                token = hashlib.sha256(f"{username}:kingmailer".encode()).hexdigest()
                
                result = {
                    'success': True,
                    'message': 'Login successful',
                    'token': token,
                    'user': username
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            else:
                self.send_response(401)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Invalid username or password'
                }).encode())
        
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False,
                'error': str(e)
            }).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
