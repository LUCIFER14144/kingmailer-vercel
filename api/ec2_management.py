"""
KINGMAILER v4.0 - EC2 Management API
Full AWS EC2 integration: Create, manage, and terminate instances
Send emails through EC2 IPs using SMTP
"""

from http.server import BaseHTTPRequestHandler
import json
import boto3
from botocore.exceptions import ClientError
import time

# In-memory storage for EC2 instances and credentials
EC2_INSTANCES = []
AWS_CREDENTIALS = None


def get_latest_amazon_linux_ami(ec2_client):
    """Get the latest Amazon Linux 2 AMI ID for the region"""
    try:
        response = ec2_client.describe_images(
            Owners=['amazon'],
            Filters=[
                {'Name': 'name', 'Values': ['amzn2-ami-hvm-*-x86_64-gp2']},
                {'Name': 'state', 'Values': ['available']}
            ]
        )
        
        if not response['Images']:
            # Fallback to region-specific AMI map (as of Feb 2026)
            ami_map = {
                'us-east-1': 'ami-0277155c3f0ab2930',
                'us-west-2': 'ami-0a7d051a1c4b54f65',
                'eu-west-1': 'ami-00385a401487aefa4',
                'ap-southeast-1': 'ami-04677bdaa3c2b6e24',
                'ap-south-1': 'ami-0f58b397bc5c1f2e8'
            }
            return ami_map.get(ec2_client.meta.region_name, ami_map['us-east-1'])
        
        # Sort by creation date and get the latest
        images = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)
        return images[0]['ImageId']
    except Exception:
        # Fallback AMI map
        ami_map = {
            'us-east-1': 'ami-0277155c3f0ab2930',
            'us-west-2': 'ami-0a7d051a1c4b54f65',
            'eu-west-1': 'ami-00385a401487aefa4',
            'ap-southeast-1': 'ami-04677bdaa3c2b6e24',
            'ap-south-1': 'ami-0f58b397bc5c1f2e8'
        }
        return ami_map.get(ec2_client.meta.region_name, ami_map['us-east-1'])


def create_ec2_instance(access_key, secret_key, region, keypair_name, security_group=None):
    """Create a new EC2 instance for email sending"""
    try:
        ec2_client = boto3.client(
            'ec2',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        # Get the latest Amazon Linux 2 AMI for the region
        ami_id = get_latest_amazon_linux_ami(ec2_client)
        
        # Create default security group if not provided
        if not security_group:
            try:
                sg_response = ec2_client.create_security_group(
                    GroupName=f'kingmailer-sg-{int(time.time())}',
                    Description='KINGMAILER Email Server Security Group'
                )
                security_group = sg_response['GroupId']
                
                # Add inbound rules for SMTP ports and relay HTTP server
                ec2_client.authorize_security_group_ingress(
                    GroupId=security_group,
                    IpPermissions=[
                        {'IpProtocol': 'tcp', 'FromPort': 25, 'ToPort': 25, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 587, 'ToPort': 587, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 465, 'ToPort': 465, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 8080, 'ToPort': 8080, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
                    ]
                )
            except ClientError as e:
                if 'InvalidGroup.Duplicate' not in str(e):
                    raise
        else:
            # If custom security group provided, ensure port 8080 is open
            try:
                ec2_client.authorize_security_group_ingress(
                    GroupId=security_group,
                    IpPermissions=[
                        {'IpProtocol': 'tcp', 'FromPort': 8080, 'ToPort': 8080, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 25, 'ToPort': 25, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 587, 'ToPort': 587, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
                    ]
                )
            except ClientError as e:
                # Ignore if rules already exist
                if 'InvalidPermission.Duplicate' not in str(e):
                    pass  # Continue anyway, rules might already exist
        
        # Launch instance (t2.micro for cost-effectiveness)
        response = ec2_client.run_instances(
            ImageId=ami_id,
            InstanceType='t2.micro',
            KeyName=keypair_name,
            MinCount=1,
            MaxCount=1,
            SecurityGroupIds=[security_group],
            UserData='''#!/bin/bash
set -e
exec > >(tee /var/log/user-data.log)
exec 2>&1

echo "=== KINGMAILER EC2 Email Relay Setup Started ==="
date

# Update system
echo "Step 1: Updating system packages..."
yum update -y

# Install required packages
echo "Step 2: Installing postfix, python3, and dependencies..."
yum install -y postfix mailx python3 python3-pip

# Configure postfix
echo "Step 3: Configuring postfix..."
cat > /etc/postfix/main.cf << 'POSTFIX_EOF'
compatibility_level = 2
queue_directory = /var/spool/postfix
command_directory = /usr/sbin
daemon_directory = /usr/libexec/postfix
data_directory = /var/lib/postfix
mail_owner = postfix
inet_interfaces = all
inet_protocols = all
mydestination = $myhostname, localhost.$mydomain, localhost
unknown_local_recipient_reject_code = 550
mynetworks = 0.0.0.0/0, [::]/0
relay_domains = 
smtpd_banner = $myhostname ESMTP
smtpd_tls_cert_file = /etc/pki/tls/certs/postfix.pem
smtpd_tls_key_file = /etc/pki/tls/private/postfix.key
smtpd_use_tls = yes
smtpd_tls_session_cache_database = btree:${data_directory}/smtpd_scache
smtp_tls_session_cache_database = btree:${data_directory}/smtp_scache
POSTFIX_EOF

# Start and enable postfix
echo "Step 4: Starting postfix service..."
systemctl enable postfix
systemctl start postfix
systemctl status postfix

# Create email relay HTTP server
echo "Step 5: Creating Python email relay server..."
cat > /opt/email_relay_server.py << 'RELAY_EOF'
#!/usr/bin/env python3
import json
import smtplib
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/email_relay.log'),
        logging.StreamHandler()
    ]
)

class EmailRelayHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logging.info("%s - %s" % (self.client_address[0], format%args))
    
    def do_GET(self):
        """Health check endpoint"""
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'status': 'healthy',
                'service': 'KINGMAILER Email Relay',
                'timestamp': datetime.now().isoformat(),
                'postfix_running': self.check_postfix()
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """Email relay endpoint"""
        if self.path == '/relay':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                from_name = data.get('from_name', 'KINGMAILER')
                from_email = data.get('from_email', 'noreply@relay.local')
                to_email = data.get('to', '')
                subject = data.get('subject', 'No Subject')
                html_body = data.get('html', '')
                
                if not to_email:
                    raise ValueError('Recipient email required')
                
                # Send email via local postfix
                msg = MIMEMultipart('alternative')
                msg['From'] = f"{from_name} <{from_email}>"
                msg['To'] = to_email
                msg['Subject'] = subject
                msg.attach(MIMEText(html_body, 'html'))
                
                with smtplib.SMTP('localhost', 25) as server:
                    server.send_message(msg)
                
                logging.info(f"Email sent successfully to {to_email}")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'message': 'Email sent'}).encode())
                
            except Exception as e:
                logging.error(f"Error sending email: {str(e)}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def check_postfix(self):
        """Check if postfix is running"""
        try:
            import subprocess
            result = subprocess.run(['systemctl', 'is-active', 'postfix'], 
                                    capture_output=True, text=True)
            return result.stdout.strip() == 'active'
        except:
            return False

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8080), EmailRelayHandler)
    logging.info('Email Relay Server started on port 8080')
    logging.info('Health check: http://<ip>:8080/health')
    logging.info('Relay endpoint: http://<ip>:8080/relay')
    server.serve_forever()
RELAY_EOF

chmod +x /opt/email_relay_server.py

# Create systemd service for relay server
echo "Step 6: Creating systemd service..."
cat > /etc/systemd/system/email-relay.service << 'SERVICE_EOF'
[Unit]
Description=KINGMAILER Email Relay HTTP Server
After=network.target postfix.service
Requires=postfix.service

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/email_relay_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Start and enable relay service
echo "Step 7: Starting email relay service..."
systemctl daemon-reload
systemctl enable email-relay.service
systemctl start email-relay.service
systemctl status email-relay.service

# Configure firewall (if firewalld is running)
if systemctl is-active --quiet firewalld; then
    echo "Step 8: Configuring firewall..."
    firewall-cmd --permanent --add-port=25/tcp
    firewall-cmd --permanent --add-port=587/tcp
    firewall-cmd --permanent --add-port=8080/tcp
    firewall-cmd --reload
fi

echo "=== KINGMAILER EC2 Email Relay Setup Complete ==="
echo "Health Check: curl http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8080/health"
date
            ''',
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': 'KINGMAILER-Email-Server'},
                    {'Key': 'Purpose', 'Value': 'Email Relay'}
                ]
            }]
        )
        
        instance_id = response['Instances'][0]['InstanceId']
        
        # Wait for instance to get public IP
        time.sleep(10)
        
        # Get instance details
        instances = ec2_client.describe_instances(InstanceIds=[instance_id])
        instance = instances['Reservations'][0]['Instances'][0]
        public_ip = instance.get('PublicIpAddress', 'Pending...')
        
        return {
            'success': True,
            'instance_id': instance_id,
            'public_ip': public_ip,
            'region': region,
            'state': instance['State']['Name']
        }
    
    except ClientError as e:
        return {
            'success': False,
            'error': f'AWS Error: {e.response["Error"]["Message"]}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def terminate_ec2_instance(access_key, secret_key, region, instance_id):
    """Terminate an EC2 instance"""
    try:
        ec2_client = boto3.client(
            'ec2',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        ec2_client.terminate_instances(InstanceIds=[instance_id])
        
        return {
            'success': True,
            'message': f'Instance {instance_id} terminated successfully'
        }
    
    except ClientError as e:
        return {
            'success': False,
            'error': f'AWS Error: {e.response["Error"]["Message"]}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def list_ec2_instances(access_key, secret_key, region):
    """List all EC2 instances"""
    try:
        ec2_client = boto3.client(
            'ec2',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        response = ec2_client.describe_instances(
            Filters=[
                {'Name': 'tag:Purpose', 'Values': ['Email Relay']},
                {'Name': 'instance-state-name', 'Values': ['running', 'pending', 'stopping', 'stopped']}
            ]
        )
        
        instances = []
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instances.append({
                    'instance_id': instance['InstanceId'],
                    'public_ip': instance.get('PublicIpAddress', 'N/A'),
                    'private_ip': instance.get('PrivateIpAddress', 'N/A'),
                    'state': instance['State']['Name'],
                    'instance_type': instance['InstanceType'],
                    'launch_time': str(instance['LaunchTime']),
                    'created_at': str(instance['LaunchTime']),  # Alias for frontend compatibility
                    'region': region  # Include region from credentials
                })
        
        return {
            'success': True,
            'instances': instances,
            'count': len(instances)
        }
    
    except ClientError as e:
        return {
            'success': False,
            'error': f'AWS Error: {e.response["Error"]["Message"]}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Get EC2 instances or credentials"""
        try:
            global AWS_CREDENTIALS, EC2_INSTANCES
            
            if self.path == '/api/ec2_management':
                # If credentials exist, fetch live instances from AWS
                if AWS_CREDENTIALS:
                    live_result = list_ec2_instances(
                        AWS_CREDENTIALS['access_key'],
                        AWS_CREDENTIALS['secret_key'],
                        AWS_CREDENTIALS['region']
                    )
                    
                    if live_result.get('success'):
                        # Update in-memory instances with live data
                        EC2_INSTANCES = live_result['instances']
                        result = {
                            'success': True,
                            'instances': EC2_INSTANCES,
                            'has_credentials': True
                        }
                    else:
                        # AWS call failed, return stored instances
                        result = {
                            'success': True,
                            'instances': EC2_INSTANCES,
                            'has_credentials': True,
                            'warning': 'Could not fetch live instances from AWS'
                        }
                else:
                    # No credentials, return empty list
                    result = {
                        'success': True,
                        'instances': [],
                        'has_credentials': False,
                        'message': 'Please save AWS credentials first'
                    }
            elif self.path == '/api/ec2_management/credentials':
                # Return credentials (without secret key)
                if AWS_CREDENTIALS:
                    result = {
                        'success': True,
                        'credentials': {
                            'region': AWS_CREDENTIALS.get('region'),
                            'keypair': AWS_CREDENTIALS.get('keypair'),
                            'has_access_key': bool(AWS_CREDENTIALS.get('access_key'))
                        }
                    }
                else:
                    result = {
                        'success': True,
                        'credentials': None
                    }
            else:
                result = {'success': False, 'error': 'Unknown endpoint'}
            
            self.send_response(200)
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
    
    def do_POST(self):
        """Create instance or save credentials"""
        try:
            global AWS_CREDENTIALS, EC2_INSTANCES
            
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            action = data.get('action')
            
            if action == 'save_credentials':
                # Save AWS credentials
                AWS_CREDENTIALS = {
                    'access_key': data.get('access_key'),
                    'secret_key': data.get('secret_key'),
                    'region': data.get('region', 'us-east-1'),
                    'keypair': data.get('keypair'),
                    'security_group': data.get('security_group', '')
                }
                
                result = {
                    'success': True,
                    'message': 'AWS credentials saved successfully'
                }
            
            elif action == 'create_instance':
                # Create EC2 instance
                if not AWS_CREDENTIALS:
                    result = {
                        'success': False,
                        'error': 'Please save AWS credentials first'
                    }
                else:
                    create_result = create_ec2_instance(
                        AWS_CREDENTIALS['access_key'],
                        AWS_CREDENTIALS['secret_key'],
                        AWS_CREDENTIALS['region'],
                        AWS_CREDENTIALS['keypair'],
                        AWS_CREDENTIALS.get('security_group')
                    )
                    
                    if create_result.get('success'):
                        # Add to instances list
                        EC2_INSTANCES.append({
                            'id': len(EC2_INSTANCES) + 1,
                            'instance_id': create_result['instance_id'],
                            'public_ip': create_result['public_ip'],
                            'region': create_result['region'],
                            'state': create_result['state'],
                            'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
                        })
                        
                        # Return wrapped result for frontend
                        result = {
                            'success': True,
                            'instance': {
                                'instance_id': create_result['instance_id'],
                                'public_ip': create_result['public_ip'],
                                'region': create_result['region'],
                                'state': create_result['state']
                            }
                        }
                    else:
                        # Pass through error
                        result = create_result
            
            elif action == 'list_instances':
                # List all EC2 instances from AWS
                if not AWS_CREDENTIALS:
                    result = {
                        'success': False,
                        'error': 'Please save AWS credentials first'
                    }
                else:
                    result = list_ec2_instances(
                        AWS_CREDENTIALS['access_key'],
                        AWS_CREDENTIALS['secret_key'],
                        AWS_CREDENTIALS['region']
                    )
            
            else:
                result = {'success': False, 'error': 'Unknown action'}
            
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
    
    def do_DELETE(self):
        """Terminate EC2 instance"""
        try:
            global AWS_CREDENTIALS, EC2_INSTANCES
            
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body)
            
            instance_id = data.get('instance_id')
            
            if not instance_id:
                result = {'success': False, 'error': 'Instance ID required'}
            elif not AWS_CREDENTIALS:
                result = {'success': False, 'error': 'AWS credentials not configured'}
            else:
                result = terminate_ec2_instance(
                    AWS_CREDENTIALS['access_key'],
                    AWS_CREDENTIALS['secret_key'],
                    AWS_CREDENTIALS['region'],
                    instance_id
                )
                
                if result['success']:
                    # Remove from instances list
                    EC2_INSTANCES = [i for i in EC2_INSTANCES if i.get('instance_id') != instance_id]
            
            self.send_response(200)
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
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
