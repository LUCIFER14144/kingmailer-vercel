"""
KINGMAILER v4.0 - Bulk Email Sending API  
Vercel Serverless Function for CSV bulk sending with template replacement
"""

from http.server import BaseHTTPRequestHandler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import boto3
from botocore.exceptions import ClientError
import csv
import io
import time
import random
import re
import json


def replace_tags(template, data):
    """Replace {{tag}} placeholders with data from CSV"""
    def replacer(match):
        key = match.group(1)
        return str(data.get(key, match.group(0)))
    
    return re.sub(r'\{\{(\w+)\}\}', replacer, template)


def send_email_smtp(smtp_config, to_email, subject, html_body, text_body=""):
    """Send single email via SMTP"""
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
        
        return {'success': True}
    
    except Exception as e:
        return {'success': False, 'error': str(e)}


def send_email_ses(aws_config, to_email, subject, html_body, text_body=""):
    """Send single email via AWS SES"""
    try:
        ses_client = boto3.client(
            'ses',
            region_name=aws_config.get('region', 'us-east-1'),
            aws_access_key_id=aws_config.get('access_key'),
            aws_secret_access_key=aws_config.get('secret_key')
        )
        
        ses_client.send_email(
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
        
        return {'success': True}
    
    except Exception as e:
        return {'success': False, 'error': str(e)}


class SMTPPool:
    """SMTP account rotation manager"""
    def __init__(self, accounts):
        self.accounts = accounts if isinstance(accounts, list) else [accounts]
        self.current_index = 0
    
    def get_next(self):
        """Get next SMTP account with round-robin"""
        if not self.accounts:
            return None
        
        account = self.accounts[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.accounts)
        return account


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Bulk email sending with CSV upload"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            csv_data = data.get('csv_data', '')
            subject_template = data.get('subject', 'No Subject')
            html_template = data.get('html', '')
            text_template = data.get('text', '')
            send_method = data.get('method', 'smtp')
            
            min_delay = int(data.get('min_delay', 2000))
            max_delay = int(data.get('max_delay', 5000))
            
            if not csv_data:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'CSV data required'}).encode())
                return
            
            csv_file = io.StringIO(csv_data)
            reader = csv.DictReader(csv_file)
            recipients = list(reader)
            
            if not recipients:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'No recipients in CSV'}).encode())
                return
            
            results = {
                'total': len(recipients),
                'sent': 0,
                'failed': 0,
                'errors': [],
                'skipped': []
            }
            
            smtp_pool = None
            if send_method == 'smtp' or send_method == 'gmail':
                smtp_configs = data.get('smtp_configs', [])
                if not smtp_configs:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'SMTP config required'}).encode())
                    return
                smtp_pool = SMTPPool(smtp_configs)
            
            aws_config = None
            if send_method == 'ses':
                aws_config = data.get('aws_config')
                if not aws_config:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'AWS config required'}).encode())
                    return
            
            for idx, recipient in enumerate(recipients):
                email = recipient.get('email') or recipient.get('Email') or recipient.get('EMAIL')
                
                if not email or '@' not in email:
                    results['skipped'].append(recipient)
                    continue
                
                subject = replace_tags(subject_template, recipient)
                html_body = replace_tags(html_template, recipient)
                text_body = replace_tags(text_template, recipient) if text_template else ""
                
                send_result = None
                
                if send_method == 'smtp' or send_method == 'gmail':
                    smtp_config = smtp_pool.get_next()
                    send_result = send_email_smtp(smtp_config, email, subject, html_body, text_body)
                
                elif send_method == 'ses':
                    send_result = send_email_ses(aws_config, email, subject, html_body, text_body)
                
                if send_result and send_result['success']:
                    results['sent'] += 1
                else:
                    results['failed'] += 1
                    error_msg = send_result.get('error', 'Unknown error') if send_result else 'No result'
                    results['errors'].append({'email': email, 'error': error_msg})
                
                if idx < len(recipients) - 1:
                    delay_ms = random.randint(min_delay, max_delay)
                    time.sleep(delay_ms / 1000.0)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'message': f'Bulk sending completed: {results["sent"]} sent, {results["failed"]} failed',
                'results': results
            }).encode())
        
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
