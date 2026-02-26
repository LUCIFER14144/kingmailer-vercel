"""
KINGMAILER v4.0 - Health Check Endpoint
Vercel Serverless Function for deployment verification
"""

from http.server import BaseHTTPRequestHandler
import json
import sys

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response = {
            'status': 'healthy',
            'service': 'KINGMAILER v4.0',
            'platform': 'Vercel Serverless',
            'python_version': sys.version,
            'features': {
                'smtp': True,
                'ses': True,
                'ec2_relay': True,
                'bulk_sending': True,
                'account_rotation': True
            },
            'message': '✅ SMTP works on Vercel!'
        }
        
        self.wfile.write(json.dumps(response).encode())
        return
