"""
Account Statistics API Endpoint
Provides account stats, send counts, and status tracking
"""

import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Get account statistics"""
        try:
            # Mock account statistics for now
            # In a real implementation, this would read from a database or file
            account_stats = {
                "smtp": {},
                "gmail_api": {},
                "ses": {}
            }
            
            # Try to load existing stats from file (if it exists)
            stats_file = '/tmp/kingmailer_account_stats.json'
            if os.path.exists(stats_file):
                try:
                    with open(stats_file, 'r') as f:
                        account_stats = json.load(f)
                except:
                    pass
            
            response_data = {
                "success": True,
                "accountStats": account_stats,
                "timestamp": datetime.now().isoformat()
            }
            
            # Set CORS headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
            
            self.wfile.write(json.dumps(response_data).encode())
            
        except Exception as e:
            # Error response
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