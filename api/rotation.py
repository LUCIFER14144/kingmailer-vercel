"""
KINGMAILER v4.0 - Subject/Body Rotation API
Manages subject and body templates for rotation
"""

from http.server import BaseHTTPRequestHandler
import json

# In-memory storage for subjects and bodies
ROTATION_STORE = {
    'subjects': [],
    'bodies': []
}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Get all subjects and bodies"""
        try:
            result = {
                'success': True,
                'data': ROTATION_STORE
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
        """Add subjects or bodies"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            rotation_type = data.get('type')  # 'subject' or 'body'
            items = data.get('items', [])  # List of strings or single string
            
            if not rotation_type or rotation_type not in ['subject', 'body']:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Type must be "subject" or "body"'
                }).encode())
                return
            
            # Handle single item or list
            if isinstance(items, str):
                items = [items]
            
            if not items:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'No items provided'
                }).encode())
                return
            
            # Add to appropriate list
            if rotation_type == 'subject':
                ROTATION_STORE['subjects'].extend(items)
                added_count = len(items)
                total = len(ROTATION_STORE['subjects'])
            else:
                ROTATION_STORE['bodies'].extend(items)
                added_count = len(items)
                total = len(ROTATION_STORE['bodies'])
            
            result = {
                'success': True,
                'message': f'Added {added_count} {rotation_type}(s). Total: {total}',
                'total': total
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
        """Clear subjects or bodies"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            rotation_type = data.get('type')  # 'subject', 'body', or 'all'
            
            if rotation_type == 'subject':
                ROTATION_STORE['subjects'] = []
                message = 'Cleared all subjects'
            elif rotation_type == 'body':
                ROTATION_STORE['bodies'] = []
                message = 'Cleared all bodies'
            elif rotation_type == 'all':
                ROTATION_STORE['subjects'] = []
                ROTATION_STORE['bodies'] = []
                message = 'Cleared all subjects and bodies'
            else:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Type must be "subject", "body", or "all"'
                }).encode())
                return
            
            result = {
                'success': True,
                'message': message
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
