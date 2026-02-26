"""
KINGMAILER v4.0 - EC2 Relay Management API
Manages EC2 relay endpoints for email sending
"""

from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import socket

# In-memory storage for EC2 relays
EC2_RELAYS = []

def test_ec2_endpoint(url):
    """Test if EC2 endpoint is reachable"""
    try:
        # Try to connect to the endpoint
        req = urllib.request.Request(url, method='GET')
        req.add_header('User-Agent', 'KINGMAILER/4.0')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.getcode()
            return {
                'success': True,
                'status_code': status,
                'message': f'Connection successful (HTTP {status})'
            }
    
    except urllib.error.HTTPError as e:
        return {
            'success': False,
            'error': f'HTTP Error {e.code}: {e.reason}'
        }
    except urllib.error.URLError as e:
        return {
            'success': False,
            'error': f'Connection failed: {str(e.reason)}'
        }
    except socket.timeout:
        return {
            'success': False,
            'error': 'Connection timeout'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def send_via_ec2(relay_url, sender_name, sender_email, recipient, subject, html_body):
    """Send email through EC2 relay endpoint"""
    try:
        payload = {
            'from_name': sender_name,
            'from_email': sender_email,
            'to': recipient,
            'subject': subject,
            'html': html_body
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(relay_url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('User-Agent', 'KINGMAILER/4.0')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return {
                'success': True,
                'message': 'Email sent via EC2',
                'details': result
            }
    
    except Exception as e:
        return {
            'success': False,
            'error': f'EC2 relay failed: {str(e)}'
        }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Get all EC2 relays"""
        try:
            result = {
                'success': True,
                'relays': EC2_RELAYS,
                'count': len(EC2_RELAYS)
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
        """Add EC2 relay or test connection"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            action = data.get('action', 'add')  # 'add' or 'test'
            
            if action == 'test':
                # Test connection to EC2 endpoint
                url = data.get('url')
                if not url:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'success': False,
                        'error': 'URL required for testing'
                    }).encode())
                    return
                
                test_result = test_ec2_endpoint(url)
                
                self.send_response(200 if test_result['success'] else 400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(test_result).encode())
                return
            
            # Add new EC2 relay
            url = data.get('url')
            label = data.get('label', '')
            
            if not url:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Relay URL is required'
                }).encode())
                return
            
            # Check if already exists
            for relay in EC2_RELAYS:
                if relay['url'] == url:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'success': False,
                        'error': 'This EC2 relay already exists'
                    }).encode())
                    return
            
            # Add relay
            relay_id = len(EC2_RELAYS) + 1
            new_relay = {
                'id': relay_id,
                'url': url,
                'label': label or f'EC2 Relay #{relay_id}',
                'status': 'active'
            }
            
            EC2_RELAYS.append(new_relay)
            
            result = {
                'success': True,
                'message': f'EC2 relay added successfully',
                'relay': new_relay
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
        """Remove EC2 relay"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            relay_id = data.get('id')
            
            if not relay_id:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Relay ID required'
                }).encode())
                return
            
            # Find and remove relay
            global EC2_RELAYS
            original_count = len(EC2_RELAYS)
            EC2_RELAYS = [r for r in EC2_RELAYS if r['id'] != relay_id]
            
            if len(EC2_RELAYS) < original_count:
                result = {
                    'success': True,
                    'message': 'EC2 relay removed successfully'
                }
            else:
                result = {
                    'success': False,
                    'error': 'EC2 relay not found'
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
