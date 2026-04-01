"""
Gmail OAuth2 Token Exchange API
Exchanges authorization code for access_token and refresh_token
Supports both Web and Desktop app credentials
"""

from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import urllib.error
import urllib.parse


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            code = data.get('code', '').strip()
            client_id = data.get('client_id', '').strip()
            client_secret = data.get('client_secret', '').strip()
            redirect_uri = data.get('redirect_uri', '').strip()
            token_uri = data.get('token_uri', 'https://oauth2.googleapis.com/token').strip()
            
            if not all([code, client_id, client_secret, redirect_uri]):
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Missing required fields: code, client_id, client_secret, redirect_uri'
                }).encode())
                return

            # Safety: only allow Google OAuth token endpoints
            if not (token_uri.startswith('https://oauth2.googleapis.com/') or token_uri.startswith('https://accounts.google.com/o/oauth2/')):
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': 'Invalid token_uri. Must be a Google OAuth token endpoint.'
                }).encode())
                return
            
            # Exchange authorization code for tokens
            # Works with both Desktop (urn:ietf:wg:oauth:2.0:oob) and Web app redirects
            token_url = token_uri
            payload = {
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'
            }
            
            encoded_data = urllib.parse.urlencode(payload).encode('utf-8')
            req = urllib.request.Request(token_url, data=encoded_data, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')
            
            try:
                with urllib.request.urlopen(req, timeout=15) as response:
                    resp_data = json.loads(response.read().decode('utf-8'))
                    
                    access_token = resp_data.get('access_token')
                    refresh_token = resp_data.get('refresh_token')
                    expires_in = resp_data.get('expires_in')
                    
                    if not access_token:
                        self.send_response(400)
                        self.send_header('Content-type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'success': False,
                            'error': 'No access_token in response from Google'
                        }).encode())
                        return
                    
                    # Get user email from Google
                    user_email = self._get_user_email(access_token)
                    
                    # Success response
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'success': True,
                        'access_token': access_token,
                        'refresh_token': refresh_token,
                        'expires_in': expires_in,
                        'user_email': user_email
                    }).encode())
                    
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8') if e.fp else str(e)
                self.send_response(e.code)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': False,
                    'error': f'Google token exchange failed (HTTP {e.code}): {error_body}'
                }).encode())
                
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False,
                'error': f'Server error: {str(e)}'
            }).encode())
    
    def _get_user_email(self, access_token):
        """Get user's email address from Google"""
        try:
            userinfo_url = 'https://www.googleapis.com/oauth2/v2/userinfo'
            req = urllib.request.Request(userinfo_url)
            req.add_header('Authorization', f'Bearer {access_token}')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return data.get('email', '')
        except:
            return ''
