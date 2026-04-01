"""
Account Reactivation API Endpoint
Reactivates deactivated accounts
"""

import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Reactivate all deactivated accounts"""
        try:
            # Load existing stats from file
            stats_file = '/tmp/kingmailer_account_stats.json'
            account_stats = {
                "smtp": {},
                "gmail_api": {},
                "ses": {}
            }
            
            if os.path.exists(stats_file):
                try:
                    with open(stats_file, 'r') as f:
                        account_stats = json.load(f)
                except:
                    pass
            
            reactivated_count = 0
            
            # Reactivate SMTP accounts
            for smtp_user in account_stats.get("smtp", {}):
                if not account_stats["smtp"][smtp_user].get("is_active", True):
                    account_stats["smtp"][smtp_user]["is_active"] = True
                    account_stats["smtp"][smtp_user]["failed_attempts"] = 0
                    reactivated_count += 1
            
            # Reactivate Gmail API accounts 
            for gmail_email in account_stats.get("gmail_api", {}):
                if not account_stats["gmail_api"][gmail_email].get("is_active", True):
                    account_stats["gmail_api"][gmail_email]["is_active"] = True
                    account_stats["gmail_api"][gmail_email]["failed_attempts"] = 0
                    reactivated_count += 1
            
            # Reactivate SES accounts
            for ses_name in account_stats.get("ses", {}):
                if not account_stats["ses"][ses_name].get("is_active", True):
                    account_stats["ses"][ses_name]["is_active"] = True
                    account_stats["ses"][ses_name]["failed_attempts"] = 0
                    reactivated_count += 1
            
            # Save updated stats back to file
            try:
                os.makedirs(os.path.dirname(stats_file), exist_ok=True)
                with open(stats_file, 'w') as f:
                    json.dump(account_stats, f)
            except:
                pass
            
            response_data = {
                "success": True,
                "reactivated_count": reactivated_count,
                "message": f"{reactivated_count} accounts have been reactivated",
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