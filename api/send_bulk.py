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
import urllib.error
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
    first_names = ['James', 'John', 'Robert', 'Michael', 'William', 'David', 'Richard', 'Joseph', 'Thomas', 'Christopher',
                  'Mary', 'Patricia', 'Jennifer', 'Linda', 'Elizabeth', 'Barbara', 'Susan', 'Jessica', 'Sarah', 'Karen',
                  'Nancy', 'Betty', 'Helen', 'Sandra', 'Donna', 'Carol', 'Ruth', 'Sharon', 'Michelle', 'Laura']
    last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez',
                 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore', 'Jackson', 'White']
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def gen_company():
    prefixes = ['Tech', 'Global', 'Digital', 'Smart', 'Innovative', 'Advanced', 'Premier', 'Elite', 'Prime', 'Strategic']
    suffixes = ['Solutions', 'Systems', 'Corporation', 'Industries', 'Group', 'Services', 'Technologies', 'Dynamics', 'Ventures', 'Partners']
    return f"{random.choice(prefixes)} {random.choice(suffixes)}"

def gen_us_company():
    company_types = ['Inc.', 'LLC', 'Corp.', 'Co.', 'Ltd.']
    business_names = ['Apple Valley', 'Cedar Creek', 'Golden Gate', 'Silver Lake', 'Mountain View', 'River Ridge', 
                     'Sunset', 'Pioneer', 'Heritage', 'Liberty', 'Victory', 'Summit', 'Crown', 'Royal', 'Imperial']
    business_types = ['Marketing', 'Consulting', 'Software', 'Financial', 'Medical', 'Legal', 'Real Estate', 
                     'Insurance', 'Construction', 'Manufacturing', 'Retail', 'Healthcare', 'Education']
    return f"{random.choice(business_names)} {random.choice(business_types)} {random.choice(company_types)}"

def gen_address():
    street_nums = random.randint(100, 9999)
    street_names = ['Main St', 'Oak Ave', 'Pine St', 'Cedar Ln', 'Elm Way', 'Maple Dr', 'First St', 'Second Ave', 
                   'Market St', 'Washington Blvd', 'Lincoln Ave', 'Jefferson St', 'Madison Dr', 'Monroe Way']
    return f"{street_nums} {random.choice(street_names)}"

def gen_city():
    cities = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia', 'San Antonio', 'San Diego',
             'Dallas', 'San Jose', 'Austin', 'Jacksonville', 'Fort Worth', 'Columbus', 'Charlotte', 'Seattle',
             'Denver', 'Boston', 'Nashville', 'Detroit', 'Portland', 'Las Vegas', 'Memphis', 'Louisville']
    return random.choice(cities)

def gen_state():
    states = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS',
             'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY',
             'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
    return random.choice(states)

def gen_zipcode():
    return f"{random.randint(10000, 99999)}"

def gen_full_address():
    return f"{gen_address()}, {gen_city()}, {gen_state()} {gen_zipcode()}"

def gen_tracking_number():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))

def gen_order_number():
    return f"ORD-{random.randint(100000, 999999)}"

def gen_reference_id():
    return f"REF{random.randint(10000, 99999)}"

def gen_13_digit():
    timestamp = int(datetime.now().timestamp() * 1000)
    random_suffix = random.randint(100, 999)
    id_str = f"{timestamp}{random_suffix}"
    return id_str[:13]

def gen_phone():
    area = random.randint(200, 999)
    exchange = random.randint(200, 999)
    number = random.randint(1000, 9999)
    return f"({area}) {exchange}-{number}"

def gen_website():
    domains = ['com', 'net', 'org', 'info', 'biz']
    prefixes = ['www', 'shop', 'secure', 'portal', 'app']
    names = ['techco', 'bizpro', 'smartsys', 'digitech', 'innovate']
    return f"https://{random.choice(prefixes)}.{random.choice(names)}.{random.choice(domains)}"


def replace_template_tags(text, row_data, recipient_email=''):
    """Replace template tags including CSV column data with comprehensive placeholder system"""
    if not text:
        return text
    
    # First replace CSV column placeholders
    for key, value in row_data.items():
        text = re.sub(r'\{\{' + key + r'\}\}', str(value), text, flags=re.IGNORECASE)
        text = re.sub(r'\{' + key + r'\}', str(value), text, flags=re.IGNORECASE)
    
    # Then replace standard template tags (generate fresh for each email)
    replacements = {
        # Recipient Tags
        'name': gen_random_name(),
        'first_name': random.choice(['James', 'John', 'Robert', 'Michael', 'William', 'Mary', 'Patricia', 'Jennifer', 'Linda', 'Elizabeth']),
        'last_name': random.choice(['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez']),
        'email': recipient_email,
        'recipient': recipient_email,
        'customer_name': gen_random_name(),
        
        # Date & Time Tags  
        'date': datetime.now().strftime('%B %d, %Y'),
        'short_date': datetime.now().strftime('%m/%d/%Y'),
        'time': datetime.now().strftime('%I:%M %p'),
        'time_24': datetime.now().strftime('%H:%M'),
        'year': str(datetime.now().year),
        'month': datetime.now().strftime('%B'),
        'day': datetime.now().strftime('%d'),
        'weekday': datetime.now().strftime('%A'),
        'timestamp': str(int(datetime.now().timestamp())),
        
        # Unique Identifier Tags
        '13_digit': gen_13_digit(),
        'unique_id': gen_13_digit(),
        'tracking_number': gen_tracking_number(),
        'order_number': gen_order_number(),
        'reference_id': gen_reference_id(),
        'transaction_id': f"TXN{random.randint(100000, 999999)}",
        'invoice_number': f"INV-{random.randint(10000, 99999)}",
        'confirmation_code': ''.join(random.choices(string.ascii_uppercase + string.digits, k=8)),
        
        # Random String Tags
        'random_6': ''.join(random.choices(string.ascii_letters + string.digits, k=6)),
        'random_8': ''.join(random.choices(string.ascii_letters + string.digits, k=8)),
        'random_10': ''.join(random.choices(string.ascii_letters + string.digits, k=10)),
        'random_upper_4': ''.join(random.choices(string.ascii_uppercase, k=4)),
        'random_upper_6': ''.join(random.choices(string.ascii_uppercase, k=6)),
        'random_lower_4': ''.join(random.choices(string.ascii_lowercase, k=4)),
        'random_lower_6': ''.join(random.choices(string.ascii_lowercase, k=6)),
        'random_digits_4': ''.join(random.choices(string.digits, k=4)),
        'random_digits_6': ''.join(random.choices(string.digits, k=6)),
        
        # Company Tags
        'company': gen_company(),
        'company_name': gen_company(),
        'random_name': gen_random_name(),
        'us_company': gen_us_company(),
        'business_name': gen_us_company(),
        
        # Address Tags
        'street_address': gen_address(),
        'city': gen_city(),
        'state': gen_state(),
        'zip_code': gen_zipcode(),
        'zipcode': gen_zipcode(),
        'full_address': gen_full_address(),
        'phone': gen_phone(),
        'phone_number': gen_phone(),
        
        # Sender Tags  
        'sender_name': gen_random_name(),
        'from_name': gen_random_name(),
        'support_name': gen_random_name(),
        'rep_name': gen_random_name(),
        'agent_name': gen_random_name(),
        'manager_name': gen_random_name(),
        
        # Contact & Web Tags
        'website': gen_website(),
        'support_email': f"support@{random.choice(['company', 'business', 'service'])}.com",
        'contact_email': f"contact@{random.choice(['firm', 'group', 'solutions'])}.com",
        
        # Financial Tags
        'amount': f"${random.randint(10, 999)}.{random.randint(10, 99)}",
        'price': f"${random.randint(5, 199)}.{random.randint(0, 99):02d}",
        'discount': f"{random.randint(10, 50)}%",
        'savings': f"${random.randint(10, 100)}",
        
        # Product Tags
        'product_name': random.choice(['Premium Package', 'Professional Service', 'Business Solution', 'Elite Plan', 'Standard Package']),
        'item_count': str(random.randint(1, 10)),
        'quantity': str(random.randint(1, 5))
    }
    
    for tag, value in replacements.items():
        text = re.sub(r'\{\{' + re.escape(tag) + r'\}\}', str(value), text, flags=re.IGNORECASE)
    
    return text


def send_email_smtp(smtp_config, from_name, recipient, subject, html_body, ec2_ip=None):
    """
    Send single email via SMTP DIRECTLY to Gmail/Outlook servers.
    IMPORTANT: This does NOT route through EC2! Connects directly to smtp.gmail.com.
    Email headers will show GMAIL's IP address, not EC2 or Vercel IPs.
    The ec2_ip parameter is unused and kept for backwards compatibility.
    """
    try:
        is_gmail = smtp_config.get('provider') == 'gmail'
        smtp_server = 'smtp.gmail.com' if is_gmail else smtp_config.get('host')
        smtp_port = 587 if is_gmail else int(smtp_config.get('port', 587))
        smtp_user = smtp_config.get('user')
        smtp_pass = smtp_config.get('pass')
        
        # Debug logging
        print(f'[SMTP SEND] → {recipient}')
        print(f'[SMTP SERVER] {smtp_server}:{smtp_port}')
        print(f'[SMTP AUTH] {smtp_user}')
        print(f'[EXPECTED IP] Gmail servers (NOT EC2, NOT Vercel)')
        
        # Use sender_name from config or fallback to from_name parameter
        sender_name = smtp_config.get('sender_name') or from_name
        
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{sender_name} <{smtp_user}>" if sender_name else smtp_user
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))
        
        # Direct connection to Gmail/Outlook SMTP servers (NOT through EC2 or any proxy)
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        print(f'[SMTP SUCCESS] Email sent to {recipient} via {smtp_server}')
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


def send_email_ec2(ec2_url, smtp_config, from_name, recipient, subject, html_body):
    """Send email via EC2 relay (JetMailer style - authenticated SMTP through EC2 IP)"""
    try:
        print(f'[EC2 RELAY] Sending to {recipient} via {ec2_url}')
        print(f'[EC2 RELAY] SMTP credentials: {smtp_config.get("user")}')
        print(f'[EXPECTED IP] EC2 relay server IP (from URL: {ec2_url})')
        
        payload = {
            'from_name': from_name,
            'to': recipient,
            'subject': subject,
            'html': html_body,
            'smtp_config': smtp_config  # Pass SMTP credentials to relay
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(ec2_url, data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            resp_data = json.loads(response.read().decode('utf-8'))
            return {'success': True, 'response': resp_data}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        return {'success': False, 'error': f'HTTP {e.code}: {error_body}'}
    except urllib.error.URLError as e:
        return {'success': False, 'error': f'Connection failed: {str(e.reason)}'}
    except Exception as e:
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}


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
            
            # Debug logging
            print('='*50)
            print('BULK SEND DEBUG - Backend')
            print(f'Method selected: {method}')
            print(f'SMTP configs received: {len(smtp_configs)}')
            print(f'SES configs received: {len(ses_configs)}')
            print(f'EC2 instances received: {len(ec2_instances)}')
            if ec2_instances:
                print(f'EC2 instance IPs: {[i.get("public_ip") for i in ec2_instances]}')
            print('='*50)
            
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
                    print(f'\\n[EMAIL {index+1}] Method: SMTP → {recipient}')
                    result = send_email_smtp(smtp_config, from_name, recipient, subject, html_body)
                
                elif method == 'ses' and ses_pool:
                    ses_config = ses_pool.get_next()  
                    print(f'\\n[EMAIL {index+1}] Method: SES → {recipient}')
                    result = send_email_ses(ses_config, from_name, recipient, subject, html_body)
                
                elif method == 'ec2' and ec2_pool:
                    # EC2 Relay - Route email through EC2 IP
                    # EC2 instance runs relay server on port 3000
                    ec2_instance = ec2_pool.get_next()  # type: ignore
                    smtp_config = smtp_pool.get_next() if smtp_pool else None
                    
                    print(f'\n[EMAIL {index+1}] Method: EC2 RELAY → {recipient}')
                    
                    if ec2_instance:
                        ec2_ip = ec2_instance.get('public_ip')  # type: ignore
                        if ec2_ip and ec2_ip != 'N/A' and ec2_ip != 'Pending...':
                            # Send via EC2 relay on port 3000 (user's open port)
                            relay_url = f'http://{ec2_ip}:3000/relay'
                            print(f'[EC2 RELAY] Connecting to {relay_url}')
                            result = send_email_ec2(relay_url, smtp_config, from_name, recipient, subject, html_body)
                            if result['success']:
                                result['via_ec2_ip'] = ec2_ip
                            else:
                                result['error'] = f"EC2 relay failed ({ec2_ip}:3000): {result.get('error', 'Unknown error')}"
                        else:
                            result = {'success': False, 'error': f'EC2 instance has no public IP yet'}
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
