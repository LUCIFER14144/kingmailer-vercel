"""
test_aws.py — Vercel serverless function to test AWS credentials using STS
"""
from http.server import BaseHTTPRequestHandler
import json
import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError


class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default request logging

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body   = self.rfile.read(length)
            data   = json.loads(body)
        except Exception as e:
            self._json(400, {'success': False, 'error': f'Bad request: {e}'})
            return

        access_key = data.get('access_key', '').strip()
        secret_key = data.get('secret_key', '').strip()
        region     = data.get('region', 'us-east-1').strip()

        if not access_key or not secret_key:
            self._json(400, {'success': False, 'error': 'Access key and secret key are required'})
            return

        try:
            sts = boto3.client(
                'sts',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )
            identity = sts.get_caller_identity()
            self._json(200, {
                'success': True,
                'account': identity.get('Account', ''),
                'arn':     identity.get('Arn', ''),
                'user_id': identity.get('UserId', ''),
            })

        except ClientError as e:
            code = e.response['Error']['Code']
            msg  = e.response['Error']['Message']
            self._json(200, {
                'success': False,
                'error': f'[{code}] {msg}',
            })
        except (NoCredentialsError, PartialCredentialsError) as e:
            self._json(200, {'success': False, 'error': f'Credential error: {e}'})
        except Exception as e:
            self._json(200, {'success': False, 'error': str(e)})

    def _json(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
