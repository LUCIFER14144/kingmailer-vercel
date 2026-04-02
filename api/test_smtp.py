"""
KINGMAILER v4.2 - SMTP/SES Connection Test Endpoint
Vercel Serverless Function for testing email account connections
"""

from http.server import BaseHTTPRequestHandler
import json
import smtplib
from email.mime.text import MIMEText

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            test_type = data.get('type', 'smtp')
            
            if test_type == 'smtp':
                result = self._test_smtp(data.get('smtp_config', {}))
            elif test_type == 'ses':
                result = self._test_ses(data.get('aws_config', {}))
            else:
                result = {'success': False, 'error': f'Unknown test type: {test_type}'}
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            
        except json.JSONDecodeError:
            self._send_error('Invalid JSON in request body')
        except Exception as e:
            self._send_error(f'Server error: {str(e)}')
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def _test_smtp(self, config):
        """Test SMTP connection"""
        try:
            provider = config.get('provider', 'gmail')
            user = config.get('user', '')
            password = config.get('pass', '')
            
            if not user or not password:
                return {'success': False, 'error': 'Username and password are required'}
            
            # Determine SMTP server and port based on provider
            if provider == 'gmail':
                smtp_server = 'smtp.gmail.com'
                smtp_port = 587
            elif provider == 'custom':
                smtp_server = config.get('host', '')
                smtp_port = int(config.get('port', 587))
                if not smtp_server:
                    return {'success': False, 'error': 'Custom SMTP host is required'}
            else:
                return {'success': False, 'error': f'Unknown provider: {provider}'}
            
            # Test connection
            with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(user, password)
            
            return {
                'success': True,
                'message': f'SMTP connection successful to {smtp_server}:{smtp_port}'
            }
            
        except smtplib.SMTPAuthenticationError:
            return {
                'success': False,
                'error': 'Authentication failed. Check your username/password or app password.'
            }
        except smtplib.SMTPConnectError:
            return {
                'success': False,
                'error': f'Failed to connect to {smtp_server}:{smtp_port}. Check server address.'
            }
        except smtplib.SMTPException as e:
            return {
                'success': False,
                'error': f'SMTP error: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Connection test failed: {str(e)}'
            }
    
    def _test_ses(self, config):
        """Test AWS SES connection"""
        try:
            access_key = config.get('access_key', '')
            secret_key = config.get('secret_key', '')
            region = config.get('region', 'us-east-1')
            
            if not access_key or not secret_key:
                return {'success': False, 'error': 'AWS Access Key and Secret Key are required'}
            
            # Test SES connection
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            ses_client = boto3.client(
                'ses',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
            
            # Test by getting send quota
            response = ses_client.get_send_quota()
            
            max_send_rate = response.get('MaxSendRate', 0)
            max_24_hour = response.get('Max24HourSend', 0)
            sent_last_24 = response.get('SentLast24Hours', 0)
            
            return {
                'success': True,
                'message': f'AWS SES connection successful in {region}',
                'quota': {
                    'max_send_rate': max_send_rate,
                    'max_24_hour': max_24_hour,
                    'sent_last_24': sent_last_24,
                    'remaining': max_24_hour - sent_last_24
                }
            }
            
        except NoCredentialsError:
            return {
                'success': False,
                'error': 'Invalid AWS credentials. Check your Access Key and Secret Key.'
            }
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            
            if error_code == 'InvalidClientTokenId':
                return {
                    'success': False,
                    'error': 'Invalid AWS Access Key ID'
                }
            elif error_code == 'SignatureDoesNotMatch':
                return {
                    'success': False,
                    'error': 'Invalid AWS Secret Access Key'
                }
            else:
                return {
                    'success': False,
                    'error': f'AWS SES error ({error_code}): {error_msg}'
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'SES connection test failed: {str(e)}'
            }
    
    def _send_error(self, message):
        """Send error response"""
        self.send_response(400)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({
            'success': False,
            'error': message
        }).encode())
