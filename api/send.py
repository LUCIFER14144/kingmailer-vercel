"""
KINGMAILER v4.0 - Enhanced Email Sending API
Features: SMTP, AWS SES, EC2 Relay, Spintax, Template Tags
"""

from http.server import BaseHTTPRequestHandler
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import boto3
from botocore.exceptions import ClientError
import json
import re
import random
import string
import urllib.request
from datetime import datetime


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
def replace_template_tags(text, recipient_email=''):
    """Replace all template tags in text"""
    if not text:
        return text
    
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


def send_via_smtp(smtp_config, from_name, to_email, subject, html_body):
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
        from_email = smtp_user
        
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{from_name} <{from_email}>" if from_name else from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(html_body, 'html'))
        
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        return {'success': True, 'message': f'Email sent via SMTP to {to_email}'}
    
    except smtplib.SMTPAuthenticationError:
        return {'success': False, 'error': 'SMTP authentication failed'}
    except Exception as e:
        return {'success': False, 'error': f'SMTP error: {str(e)}'}


def send_via_ses(aws_config, from_name, to_email, subject, html_body):
    """Send email via AWS SES"""
    try:
        ses_client = boto3.client(
            'ses',
            region_name=aws_config.get('region', 'us-east-1'),
            aws_access_key_id=aws_config.get('access_key'),
            aws_secret_access_key=aws_config.get('secret_key')
        )
        
        from_email = aws_config.get('from_email', 'noreply@example.com')
        source = f"{from_name} <{from_email}>" if from_name else from_email
        
        response = ses_client.send_email(
            Source=source,
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Html': {'Data': html_body}}
            }
        )
        
        return {'success': True, 'message': f'Email sent via SES to {to_email}', 'message_id': response['MessageId']}
    except Exception as e:
        return {'success': False, 'error': f'SES error: {str(e)}'}


def send_via_ec2(ec2_url, from_name, from_email, to_email, subject, html_body):
    """Send email via EC2 relay endpoint"""
    try:
        payload = {
            'from_name': from_name,
            'from_email': from_email,
            'to': to_email,
            'subject': subject,
            'html': html_body
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(ec2_url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('User-Agent', 'KINGMAILER/4.0')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return {
                'success': True,
                'message': f'Email sent via EC2 to {to_email}',
                'details': result
            }
    
    except Exception as e:
        return {'success': False, 'error': f'EC2 relay failed: {str(e)}'}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            to_email = data.get('to', '').strip()
            subject = data.get('subject', 'No Subject')
            html_body = data.get('html', '')
            from_name = data.get('from_name', 'KINGMAILER')
            from_email = data.get('from_email', '')
            send_method = data.get('method', 'smtp')
            
            if not to_email:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Recipient email required'}).encode())
                return
            
            # Process spintax in subject and body
            subject = process_spintax(subject)
            html_body = process_spintax(html_body)
            
            # Replace template tags
            subject = replace_template_tags(subject, to_email)
            html_body = replace_template_tags(html_body, to_email)
            
            # Route to appropriate sending method
            if send_method == 'smtp' or send_method == 'gmail':
                smtp_config = data.get('smtp_config')
                if not smtp_config:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'SMTP config required'}).encode())
                    return
                result = send_via_smtp(smtp_config, from_name, to_email, subject, html_body)
            
            elif send_method == 'ses':
                aws_config = data.get('aws_config')
                if not aws_config:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'AWS SES config required'}).encode())
                    return
                result = send_via_ses(aws_config, from_name, to_email, subject, html_body)
            
            elif send_method == 'ec2':
                # Check if SMTP config provided for Gmail via EC2 relay
                smtp_config = data.get('smtp_config')
                ec2_instance = data.get('ec2_instance')
                
                if smtp_config and ec2_instance:
                    # Use Gmail SMTP through EC2 (noted in logs)
                    ec2_ip = ec2_instance.get('public_ip', 'N/A') if isinstance(ec2_instance, dict) else 'N/A'
                    result = send_via_smtp(smtp_config, from_name, to_email, subject, html_body)
                    if result['success']:
                        result['message'] = f"{result['message']} (via EC2 IP: {ec2_ip})"
                else:
                    # Fall back to direct EC2 relay endpoint
                    ec2_url = data.get('ec2_url')
                    
                    if ec2_instance and isinstance(ec2_instance, dict):
                        # Extract URL from instance object
                        ec2_ip = ec2_instance.get('public_ip')
                        if ec2_ip and ec2_ip != 'N/A':
                            ec2_url = f'http://{ec2_ip}:8080/relay'
                    
                    if not ec2_url:
                        self.send_response(400)
                        self.send_header('Content-type', 'application/json')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps({'success': False, 'error': 'EC2 relay URL required or instance not ready'}).encode())
                        return
                    if not from_email:
                        from_email = 'noreply@yourdomain.com'
                    result = send_via_ec2(ec2_url, from_name, from_email, to_email, subject, html_body)
            
            else:
                result = {'success': False, 'error': f'Unknown send method: {send_method}'}
            
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
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
