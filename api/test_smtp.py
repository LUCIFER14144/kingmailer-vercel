"""
KINGMAILER v4.0 - SMTP Test API
Vercel Serverless Function for testing SMTP connections
"""

from http.server import BaseHTTPRequestHandler
import smtplib
import boto3
from botocore.exceptions import ClientError
import json


def test_smtp_connection(smtp_config):
    """Test SMTP connection and authentication"""
    try:
        is_gmail = smtp_config.get('provider') == 'gmail'
        
        if is_gmail:
            smtp_server = 'smtp.gmail.com'
            smtp_port = 587
        else:
            smtp_server = smtp_config.get('host')
            smtp_port = int(smtp_config.get('port', 587))
        
        smtp_user = smtp_config.get('user')
        smtp_pass = smtp_config.get('pass')
        
        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
        
        return {
            'success': True,
            'message': f'✓ SMTP connection successful to {smtp_server}:{smtp_port}',
            'details': {
                'server': smtp_server,
                'port': smtp_port,
                'user': smtp_user,
                'tls': True
            }
        }
    
    except smtplib.SMTPAuthenticationError:
        return {
            'success': False,
            'error': 'Authentication failed. Check your username/password.',
            'fix': 'For Gmail, use App Password (not your regular password)'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Connection test failed: {str(e)}'
        }


def test_ses_connection(aws_config):
    """Test AWS SES connection"""
    try:
        ses_client = boto3.client(
            'ses',
            region_name=aws_config.get('region', 'us-east-1'),
            aws_access_key_id=aws_config.get('access_key'),
            aws_secret_access_key=aws_config.get('secret_key')
        )
        
        quota = ses_client.get_send_quota()
        
        return {
            'success': True,
            'message': '✓ AWS SES connection successful',
            'details': {
                'quota': {
                    'max_24_hour': int(quota['Max24HourSend']),
                    'max_per_second': int(quota['MaxSendRate']),
                    'sent_last_24_hours': int(quota['SentLast24Hours'])
                }
            }
        }
    
    except ClientError as e:
        return {
            'success': False,
            'error': f'SES authentication failed: {e.response["Error"]["Message"]}',
            'fix': 'Check your AWS Access Key and Secret Key'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'SES test failed: {str(e)}'
        }


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            test_type = data.get('type', 'smtp')
            
            if test_type == 'smtp' or test_type == 'gmail':
                smtp_config = data.get('smtp_config')
                if not smtp_config:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'SMTP configuration required'}).encode())
                    return
                result = test_smtp_connection(smtp_config)
            
            elif test_type == 'ses':
                aws_config = data.get('aws_config')
                if not aws_config:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'AWS configuration required'}).encode())
                    return
                result = test_ses_connection(aws_config)
            
            else:
                result = {'success': False, 'error': f'Unknown test type: {test_type}'}
            
            status_code = 200 if result['success'] else 400
            self.send_response(status_code)
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
        self.send_header('Access-Control-Allow-Methods',  'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
