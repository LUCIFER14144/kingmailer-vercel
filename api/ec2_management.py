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


def create_ec2_instance(access_key, secret_key, region, keypair_name, security_group=None):
    """Create a new EC2 instance for email sending"""
    try:
        ec2_client = boto3.client(
            'ec2',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        # Create default security group if not provided
        if not security_group:
            try:
                sg_response = ec2_client.create_security_group(
                    GroupName=f'kingmailer-sg-{int(time.time())}',
                    Description='KINGMAILER Email Server Security Group'
                )
                security_group = sg_response['GroupId']
                
                # Add inbound rules for SMTP ports
                ec2_client.authorize_security_group_ingress(
                    GroupId=security_group,
                    IpPermissions=[
                        {'IpProtocol': 'tcp', 'FromPort': 25, 'ToPort': 25, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 587, 'ToPort': 587, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 465, 'ToPort': 465, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
                    ]
                )
            except ClientError as e:
                if 'InvalidGroup.Duplicate' not in str(e):
                    raise
        
        # Launch instance (t2.micro for cost-effectiveness)
        response = ec2_client.run_instances(
            ImageId='ami-0c55b159cbfafe1f0',  # Amazon Linux 2 AMI (update based on region)
            InstanceType='t2.micro',
            KeyName=keypair_name,
            MinCount=1,
            MaxCount=1,
            SecurityGroupIds=[security_group],
            UserData='''#!/bin/bash
                # Install and configure postfix for email relay
                yum update -y
                yum install -y postfix mailx
                systemctl enable postfix
                systemctl start postfix
                
                # Configure postfix for relay
                echo "relayhost = " >> /etc/postfix/main.cf
                echo "inet_interfaces = all" >> /etc/postfix/main.cf
                systemctl restart postfix
                
                # Open port 25, 587, 465 for SMTP
                iptables -A INPUT -p tcp --dport 25 -j ACCEPT
                iptables -A INPUT -p tcp --dport 587 -j ACCEPT
                iptables -A INPUT -p tcp --dport 465 -j ACCEPT
                iptables-save
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
                    'launch_time': str(instance['LaunchTime'])
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
            global AWS_CREDENTIALS
            
            if self.path == '/api/ec2_management':
                # Return stored instances
                result = {
                    'success': True,
                    'instances': EC2_INSTANCES,
                    'has_credentials': AWS_CREDENTIALS is not None
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
                    result = create_ec2_instance(
                        AWS_CREDENTIALS['access_key'],
                        AWS_CREDENTIALS['secret_key'],
                        AWS_CREDENTIALS['region'],
                        AWS_CREDENTIALS['keypair'],
                        AWS_CREDENTIALS.get('security_group')
                    )
                    
                    if result['success']:
                        EC2_INSTANCES.append({
                            'id': len(EC2_INSTANCES) + 1,
                            'instance_id': result['instance_id'],
                            'public_ip': result['public_ip'],
                            'region': result['region'],
                            'state': result['state'],
                            'created_at': time.strftime('%Y-%m-%d %H:%M:%S')
                        })
            
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
