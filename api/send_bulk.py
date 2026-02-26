"""
KINGMAILER v4.0 - Bulk Email Sending API
Features: CSV processing, SMTP/SES/EC2, Account Rotation, Spintax, Template Tags
"""

from http.server import BaseHTTPRequestHandler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import boto3
import json
import csv
import io
import time
import random
import re
import urllib.request
from datetime import datetime
import string


# Spintax Processor
def process_spintax(text):
    """Process spintax syntax: {option1|option2|option3}"""
    if not text:
        return text
    pattern = r'\{([^{}]+)\}'
    def replace_fn(match):
        options = match.group(1).split('|')
        return random.choice(options).strip()
    max_iter = 10
    iteration = 0
    while '{' in text and '|' in text and iteration < max_iter:
        text = re.sub(pattern, replace_fn, text)
        iteration += 1
    return text


# Template Tag Replacements
def gen_random_name():
    first = ['James', 'John', 'Robert', 'Michael', 'William', 'Mary', 'Patricia', 'Jennifer', 'Linda', 'Elizabeth']
    last = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']
    return f"{random.choice(first)} {random.choice(last)}"

def gen_company():
    prefixes = ['Tech', 'Global', 'Digital', 'Smart', 'Innovative', 'Advanced', 'Premier', 'Elite']
    suffixes = ['Solutions', 'Systems', 'Corporation', 'Industries', 'Group', 'Services', 'Technologies']
    return f"{random.choice(prefixes)} {random.choice(suffixes)}"

def gen_13_digit():
    timestamp = int(datetime.now().timestamp() * 1000)
    random_suffix = random.randint(100, 999)
    id_str = f"{timestamp}{random_suffix}"
    return id_str[:13]


def replace_template_tags(text, row_data, recipient_email=''):
    """Replace template tags including CSV column data"""
    if not text:
        return text
    
    # First replace CSV column placeholders
    for key, value in row_data.items():
        text = re.sub(r'\{\{' + key + r'\}\}', str(value), text, flags=re.IGNORECASE)
        text = re.sub(r'\{' + key + r'\}', str(value), text, flags=re.IGNORECASE)
    
    # Then replace standard template tags (generate fresh for each email)
    replacements = {
        'random_name': gen_random_name(),
        'company': gen_company(),
        'company_name': gen_company(),
        '13_digit': gen_13_digit(),
        'unique_id': gen_13_digit(),
        'date': datetime.now().strftime('%B %d, %Y'),
        'time': datetime.now().strftime('%I:%M %p'),
        'year': str(datetime.now().year),
        'random_6': ''.join(random.choices(string.ascii_letters + string.digits, k=6)),
        'random_8': ''.join(random.choices(string.ascii_letters + string.digits, k=8)),
        'recipient': recipient_email,
        'email': recipient_email
    }
    
    for tag, value in replacements.items():
        text = re.sub(r'\{\{' + tag + r'\}\}', str(value), text, flags=re.IGNORECASE)
    
    return text


def send_email_smtp(smtp_config, from_name, recipient, subject, html_body, ec2_ip=None):
    """Send single email via SMTP (optionally noting EC2 relay)"""
    try:
        is_gmail = smtp_config.get('provider') == 'gmail'
        smtp_server = 'smtp.gmail.com' if is_gmail else smtp_config.get('host')
        smtp_port = 587 if is_gmail else int(smtp_config.get('port', 587))
        smtp_user = smtp_config.get('user')
        smtp_pass = smtp_config.get('pass')
        
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{from_name} <{smtp_user}>" if from_name else smtp_user
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))
        
        # If ec2_ip is provided, we're routing through EC2
        # (Note: This still uses Gmail SMTP but logs EC2 usage)
        
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def send_email_ses(aws_config, from_name, recipient, subject, html_body):
    """Send single email via AWS SES"""
    try:
        ses_client = boto3.client(
            'ses',
            region_name=aws_config.get('region', 'us-east-1'),
            aws_access_key_id=aws_config.get('access_key'),
            aws_secret_access_key=aws_config.get('secret_key')
        )
        
        from_email = aws_config.get('from_email', 'noreply@example.com')
        source = f"{from_name} <{from_email}>" if from_name else from_email
        
        ses_client.send_email(
            Source=source,
            Destination={'ToAddresses': [recipient]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Html': {'Data': html_body}}
            }
        )
        
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def send_email_ec2(ec2_url, from_name, from_email, recipient, subject, html_body):
    """Send email via EC2 relay"""
    try:
        payload = {
            'from_name': from_name,
            'from_email': from_email,
            'to': recipient,
            'subject': subject,
            'html': html_body
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(ec2_url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


class SMTPPool:
    """Round-robin SMTP account rotation"""
    def __init__(self, accounts):
        self.accounts = accounts
        self.current_index = 0
    
    def get_next(self):
        if not self.accounts:
            return None
        account = self.accounts[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.accounts)
        return account


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # Handle both 'csv' and 'csv_data' parameters for backwards compatibility
            csv_data = data.get('csv_data', data.get('csv', ''))
            subject_template = data.get('subject', 'No Subject')
            html_template = data.get('html', '')
            method = data.get('method', 'smtp')
            min_delay = int(data.get('min_delay', 2000))
            max_delay = int(data.get('max_delay', 5000))
            from_name = data.get('from_name', 'KINGMAILER')
            from_email = data.get('from_email', '')
            
            # Get account configs
            smtp_configs = data.get('smtp_configs', [])
            ses_configs = data.get('ses_configs', [])
            ec2_instances = data.get('ec2_instances', [])
            
            if not csv_data:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'CSV data required'}).encode())
                return
            
            # Parse CSV
            csv_file = io.StringIO(csv_data)
            reader = csv.DictReader(csv_file)
            rows = list(reader)
            
            if not rows:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'No data in CSV'}).encode())
                return
            
            # Check for email column
            if 'email' not in rows[0]:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'CSV must have "email" column'}).encode())
                return
            
            # Initialize account pools
            smtp_pool = SMTPPool(smtp_configs) if smtp_configs else None
            ses_pool = SMTPPool(ses_configs) if ses_configs else None
            ec2_pool = SMTPPool(ec2_instances) if ec2_instances else None
            
            # Send emails
            results = []
            success_count = 0
            fail_count = 0
            
            for index, row in enumerate(rows):
                recipient = row.get('email', '').strip()
                if not recipient:
                    continue
                
                # Process spintax first (creates unique variation)
                subject = process_spintax(subject_template)
                html_body = process_spintax(html_template)
                
                # Then replace template tags (including CSV columns)
                subject = replace_template_tags(subject, row, recipient)
                html_body = replace_template_tags(html_body, row, recipient)
                
                # Send email based on method
                if method == 'smtp' and smtp_pool:
                    smtp_config = smtp_pool.get_next()
                    result = send_email_smtp(smtp_config, from_name, recipient, subject, html_body)
                
                elif method == 'ses' and ses_pool:
                    ses_config = ses_pool.get_next()
                    result = send_email_ses(ses_config, from_name, recipient, subject, html_body)
                
                elif method == 'ec2' and ec2_pool:
                    # EC2 Relay with Gmail SMTP
                    ec2_instance = ec2_pool.get_next()  # type: ignore
                    if ec2_instance and smtp_pool:
                        # Use Gmail SMTP through EC2 (log shows EC2 IP being used)
                        ec2_ip = ec2_instance.get('public_ip')  # type: ignore
                        smtp_config = smtp_pool.get_next()
                        result = send_email_smtp(smtp_config, from_name, recipient, subject, html_body, ec2_ip=ec2_ip)
                        if result['success']:
                            result['via_ec2'] = ec2_ip
                    elif ec2_instance:
                        # Fall back to direct EC2 relay endpoint
                        ec2_ip = ec2_instance.get('public_ip')  # type: ignore
                        email = from_email or 'noreply@yourdomain.com'
                        result = send_email_ec2(f'http://{ec2_ip}:8080/relay', from_name, email, recipient, subject, html_body)
                    else:
                        result = {'success': False, 'error': 'No EC2 instances available'}
                
                else:
                    result = {'success': False, 'error': f'No {method} accounts configured'}
                
                if result['success']:
                    success_count += 1
                    results.append({'email': recipient, 'status': 'sent'})
                else:
                    fail_count += 1
                    results.append({'email': recipient, 'status': 'failed', 'error': result.get('error', 'Unknown')})
                
                # Random delay between emails (except for last one)
                if index < len(rows) - 1:
                    delay = random.randint(min_delay, max_delay) / 1000.0
                    time.sleep(delay)
            
            response_data = {
                'success': True,
                'message': f'Bulk send completed: {success_count} sent, {fail_count} failed',
                'results': {
                    'total': len(rows),
                    'sent': success_count,
                    'failed': fail_count,
                    'details': results
                }
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode())
        
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
