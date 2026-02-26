"""
KINGMAILER v4.0 - Bulk Email Sending API
Vercel Serverless Function for CSV bulk sending with template replacement
"""

from flask import Flask, request, jsonify
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

app = Flask(__name__)

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


@app.route('/api/send_bulk', methods=['POST'])
def send_bulk():
    """Bulk email sending with CSV upload"""
    try:
        data = request.get_json()
        
        # Extract parameters
        csv_data = data.get('csv_data', '')
        subject_template = data.get('subject', 'No Subject')
        html_template = data.get('html', '')
        text_template = data.get('text', '')
        send_method = data.get('method', 'smtp')
        
        # Delay settings
        min_delay = int(data.get('min_delay', 2000))
        max_delay = int(data.get('max_delay', 5000))
        
        # Parse CSV
        if not csv_data:
            return jsonify({'success': False, 'error': 'CSV data is required'}), 400
        
        csv_file = io.StringIO(csv_data)
        reader = csv.DictReader(csv_file)
        recipients = list(reader)
        
        if not recipients:
            return jsonify({'success': False, 'error': 'No recipients found in CSV'}), 400
        
        # Initialize results
        results = {
            'total': len(recipients),
            'sent': 0,
            'failed': 0,
            'errors': [],
            'skipped': []
        }
        
        # Setup SMTP pool for rotation
        smtp_pool = None
        if send_method == 'smtp' or send_method == 'gmail':
            smtp_configs = data.get('smtp_configs', [])
            if not smtp_configs:
                return jsonify({'success': False, 'error': 'SMTP configuration required'}), 400
            smtp_pool = SMTPPool(smtp_configs)
        
        # AWS SES config
        aws_config = None
        if send_method == 'ses':
            aws_config = data.get('aws_config')
            if not aws_config:
                return jsonify({'success': False, 'error': 'AWS SES configuration required'}), 400
        
        # Process each recipient
        for idx, recipient in enumerate(recipients):
            # Find email field (try common variations)
            email = recipient.get('email') or recipient.get('Email') or recipient.get('EMAIL')
            
            if not email or '@' not in email:
                results['skipped'].append(recipient)
                continue
            
            # Replace template tags
            subject = replace_tags(subject_template, recipient)
            html_body = replace_tags(html_template, recipient)
            text_body = replace_tags(text_template, recipient) if text_template else ""
            
            # Send email
            send_result = None
            
            if send_method == 'smtp' or send_method == 'gmail':
                smtp_config = smtp_pool.get_next()
                send_result = send_email_smtp(smtp_config, email, subject, html_body, text_body)
            
            elif send_method == 'ses':
                send_result = send_email_ses(aws_config, email, subject, html_body, text_body)
            
            # Track result
            if send_result and send_result['success']:
                results['sent'] += 1
                print(f"✓ Sent to {email} ({results['sent']}/{results['total']})")
            else:
                results['failed'] += 1
                error_msg = send_result.get('error', 'Unknown error') if send_result else 'No send result'
                results['errors'].append({'email': email, 'error': error_msg})
                print(f"✗ Failed for {email}: {error_msg}")
            
            # Smart delay (avoid spam filters)
            if idx < len(recipients) - 1:  # Don't delay after last email
                delay_ms = random.randint(min_delay, max_delay)
                time.sleep(delay_ms / 1000.0)
        
        return jsonify({
            'success': True,
            'message': f'Bulk sending completed: {results["sent"]} sent, {results["failed"]} failed',
            'results': results
        }), 200
    
    except csv.Error as e:
        return jsonify({'success': False, 'error': f'CSV parsing error: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Bulk send failed: {str(e)}'}), 500


# Vercel serverless handler
def handler(request):
    with app.request_context(request.environ):
        return app.full_dispatch_request()
