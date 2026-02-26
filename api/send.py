"""
KINGMAILER v4.0 - SMTP Sending API
Vercel Serverless Function for sending single emails via SMTP/SES/EC2
"""

from http.server import BaseHTTPRequestHandler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import boto3
from botocore.exceptions import ClientError
import json


def send_via_smtp(smtp_config, to_email, subject, html_body, text_body=""):
    """Send email via SMTP (Gmail or custom server)"""
    try:
        is_gmail = smtp_config.get('provider') == 'gmail'
        
        if is_gmail:
            smtp_server = 'smtp.gmail.com'
            smtp_port = 587
        else:
            smtp_server = smtp_config.get('host', 'smtp.gmail.com')
            smtp_port = int(smtp_config.get('port', 587))
        
        smtp_user = smtp_config.get('user')
        smtp_pass = smtp_config.get('pass')
        
        msg = MIMEMultipart('alternative')
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        
        if text_body:
            msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        return {'success': True, 'message': f'Email sent via SMTP to {to_email}'}
    
    except smtplib.SMTPAuthenticationError:
        return {'success': False, 'error': 'SMTP authentication failed. Check your credentials.'}
    except Exception as e:
        return {'success': False, 'error': f'Error: {str(e)}'}


def send_via_ses(aws_config, to_email, subject, html_body, text_body=""):
    """Send email via AWS SES"""
    try:
        ses_client = boto3.client(
            'ses',
            region_name=aws_config.get('region', 'us-east-1'),
            aws_access_key_id=aws_config.get('access_key'),
            aws_secret_access_key=aws_config.get('secret_key')
        )
        
        response = ses_client.send_email(
            Source=aws_config.get('from_email'),
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {
                    'Html': {'Data': html_body},
                    'Text': {'Data': text_body or html_body}
                }
            }
        )
        
        return {'success': True, 'message': f'Email sent via SES to {to_email}'}
    except Exception as e:
        return {'success': False, 'error': f'SES error: {str(e)}'}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            to_email = data.get('to')
            subject = data.get('subject', 'No Subject')
            html_body = data.get('html', '')
            text_body = data.get('text', '')
            send_method = data.get('method', 'smtp')
            
            if not to_email:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Recipient email required'}).encode())
                return
            
            if send_method == 'smtp' or send_method == 'gmail':
                smtp_config = data.get('smtp_config')
                if not smtp_config:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'SMTP config required'}).encode())
                    return
                result = send_via_smtp(smtp_config, to_email, subject, html_body, text_body)
            
            elif send_method == 'ses':
                aws_config = data.get('aws_config')
                if not aws_config:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'AWS config required'}).encode())
                    return
                result = send_via_ses(aws_config, to_email, subject, html_body, text_body)
            
            else:
                result = {'success': False, 'error': f'Unknown method: {send_method}'}
            
            status_code = 200 if result['success'] else 500
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).enc

ode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

