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
                
                # Add inbound rules matching user's existing security group setup
                ec2_client.authorize_security_group_ingress(
                    GroupId=security_group,
                    IpPermissions=[
                        {'IpProtocol': 'tcp', 'FromPort': 25, 'ToPort': 25, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 587, 'ToPort': 587, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 465, 'ToPort': 465, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 3000, 'ToPort': 3000, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                        {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
                    ]
                )
            except ClientError as e:
                if 'InvalidGroup.Duplicate' not in str(e):
                    raise
        else:
            # If custom security group provided, try to add port 3000 (relay server port)
            try:
                ec2_client.authorize_security_group_ingress(
                    GroupId=security_group,
                    IpPermissions=[
                        {'IpProtocol': 'tcp', 'FromPort': 3000, 'ToPort': 3000, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
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
            UserData="""#!/bin/bash
exec > >(tee /var/log/user-data.log) 2>&1

echo "=== KINGMAILER EC2 Email Relay Setup Started ==="
date

yum update -y || dnf update -y || true
yum install -y python3 python3-pip || dnf install -y python3 || true

echo "Creating relay server..."
mkdir -p /opt

cat > /opt/email_relay_server.py << 'PYEOF'
#!/usr/bin/env python3
import json, re, smtplib, logging, socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
from datetime import datetime
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.FileHandler('/var/log/email_relay.log'), logging.StreamHandler()])
class EmailRelayHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a): logging.info("%s - %s" % (self.client_address[0], fmt%a))
    def do_GET(self):
        if self.path in ('/', '/health'):
            self.send_response(200); self.send_header('Content-type','application/json'); self.end_headers()
            def chk(p):
                try:
                    s=socket.socket(); s.settimeout(3); r=s.connect_ex(('smtp.gmail.com',p)); s.close(); return 'open' if r==0 else 'blocked'
                except: return 'unknown'
            self.wfile.write(json.dumps({'status':'healthy','service':'KINGMAILER Relay',
                'timestamp':datetime.now().isoformat(),'port_587_outbound':chk(587),'port_465_outbound':chk(465)}).encode())
        else: self.send_response(404); self.end_headers()
    def do_POST(self):
        if self.path == '/relay':
            try:
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode())
                smtp_config = data.get('smtp_config')
                if not smtp_config: raise ValueError('SMTP config required')
                to_email = data.get('to','')
                if not to_email: raise ValueError('Recipient required')
                provider = smtp_config.get('provider','gmail')
                u = smtp_config.get('user'); p = smtp_config.get('pass')
                if not u or not p: raise ValueError('SMTP credentials required')
                sname = smtp_config.get('sender_name', data.get('from_name','KINGMAILER'))
                if provider=='gmail': srv,port='smtp.gmail.com',587
                elif provider in ('outlook','hotmail'): srv,port='smtp-mail.outlook.com',587
                else: srv,port=smtp_config.get('host','smtp.gmail.com'),int(smtp_config.get('port',587))
                att=data.get('attachment')
                _html=data.get('html','')
                _plain=data.get('plain','') or re.sub('<[^>]+',' ',_html)
                _body=MIMEText(_html,'html','utf-8'); _ptxt=MIMEText(_plain,'plain','utf-8')
                if att:
                    msg=MIMEMultipart('mixed'); _alt=MIMEMultipart('alternative'); _alt.attach(_ptxt); _alt.attach(_body); msg.attach(_alt)
                else:
                    msg=MIMEMultipart('alternative'); msg.attach(_ptxt); msg.attach(_body)
                _domain=u.split('@')[-1] if '@' in u else 'mail.com'
                msg['From']="%s <%s>" % (sname,u); msg['To']=to_email; msg['Subject']=data.get('subject','')
                msg['Date']=formatdate(localtime=True)
                msg['Message-ID']=make_msgid(domain=_domain)
                msg['MIME-Version']='1.0'
                msg['List-Unsubscribe']='<mailto:unsubscribe@%s?subject=unsubscribe>' % _domain
                msg['List-Unsubscribe-Post']='List-Unsubscribe=One-Click'
                msg['Precedence']='bulk'
                msg['X-Priority']='3'
                if att:
                    try:
                        import base64 as _b64; from email.mime.base import MIMEBase; from email import encoders as _enc
                        _ac=att['content']+'='*(-len(att['content'])%4)
                        _ap=MIMEBase(*(att.get('type','application/octet-stream')+'/x').split('/')[:2])
                        _ap.set_payload(_b64.b64decode(_ac)); _enc.encode_base64(_ap)
                        _ap.add_header('Content-Disposition','attachment',filename=att.get('name','attachment'))
                        msg.attach(_ap)
                    except Exception as _ae: logging.warning("Attach err: %s" % _ae)
                with smtplib.SMTP(srv,port,timeout=30) as s:
                    s.ehlo(); s.starttls(); s.ehlo(); s.login(u,p); s.send_message(msg)
                logging.info("Sent to %s" % to_email)
                self.send_response(200); self.send_header('Content-type','application/json'); self.end_headers()
                self.wfile.write(json.dumps({'success':True,'message':'Email sent'}).encode())
            except Exception as e:
                logging.error(str(e))
                self.send_response(500); self.send_header('Content-type','application/json'); self.end_headers()
                self.wfile.write(json.dumps({'success':False,'error':str(e)}).encode())
        else: self.send_response(404); self.end_headers()
if __name__ == '__main__':
    srv = HTTPServer(('0.0.0.0',3000), EmailRelayHandler)
    logging.info('Relay started on port 3000'); srv.serve_forever()
PYEOF

chmod +x /opt/email_relay_server.py

cat > /etc/systemd/system/email-relay.service << 'SVCEOF'
[Unit]
Description=KINGMAILER Email Relay
After=network.target
[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/email_relay_server.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable email-relay.service
systemctl start email-relay.service
systemctl status email-relay.service || true

# Watchdog cron: auto-restart relay if it stops
echo '* * * * * root systemctl is-active email-relay || systemctl restart email-relay' > /etc/cron.d/email-relay-watchdog

if systemctl is-active --quiet firewalld 2>/dev/null; then
    firewall-cmd --permanent --add-port=3000/tcp || true
    firewall-cmd --permanent --add-port=587/tcp || true
    firewall-cmd --reload || true
fi

echo "=== Setup Complete ==="
date
""",
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


def restart_relay_via_ssm(access_key, secret_key, region, instance_id):
    """Use AWS SSM Run Command to reinstall and restart the relay server — no SSH needed."""
    try:
        ssm_client = boto3.client(
            'ssm',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

        # Full relay reinstall + start script sent via SSM
        setup_script = """#!/bin/bash
echo "=== KINGMAILER Relay Restart via SSM ==="
which python3 || yum install -y python3 2>/dev/null || dnf install -y python3 2>/dev/null || true
mkdir -p /opt

cat > /opt/email_relay_server.py << 'PYEOF'
#!/usr/bin/env python3
import json, re, smtplib, logging, socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
from datetime import datetime
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.FileHandler('/var/log/email_relay.log'), logging.StreamHandler()])
class EmailRelayHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a): logging.info("%s - %s" % (self.client_address[0], fmt%a))
    def do_GET(self):
        if self.path in ('/', '/health'):
            self.send_response(200); self.send_header('Content-type','application/json'); self.end_headers()
            def chk(p):
                try:
                    s=socket.socket(); s.settimeout(3); r=s.connect_ex(('smtp.gmail.com',p)); s.close(); return 'open' if r==0 else 'blocked'
                except: return 'unknown'
            self.wfile.write(json.dumps({'status':'healthy','service':'KINGMAILER Relay',
                'timestamp':datetime.now().isoformat(),'port_587_outbound':chk(587),'port_465_outbound':chk(465)}).encode())
        else: self.send_response(404); self.end_headers()
    def do_POST(self):
        if self.path == '/relay':
            try:
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode())
                smtp_config = data.get('smtp_config')
                if not smtp_config: raise ValueError('SMTP config required')
                to_email = data.get('to','')
                if not to_email: raise ValueError('Recipient required')
                provider = smtp_config.get('provider','gmail')
                u = smtp_config.get('user'); p = smtp_config.get('pass')
                if not u or not p: raise ValueError('SMTP credentials required')
                sname = smtp_config.get('sender_name', data.get('from_name','KINGMAILER'))
                if provider=='gmail': srv,port='smtp.gmail.com',587
                elif provider in ('outlook','hotmail'): srv,port='smtp-mail.outlook.com',587
                else: srv,port=smtp_config.get('host','smtp.gmail.com'),int(smtp_config.get('port',587))
                att=data.get('attachment')
                _html=data.get('html','')
                _plain=data.get('plain','') or re.sub('<[^>]+',' ',_html)
                _body=MIMEText(_html,'html','utf-8'); _ptxt=MIMEText(_plain,'plain','utf-8')
                if att:
                    msg=MIMEMultipart('mixed'); _alt=MIMEMultipart('alternative'); _alt.attach(_ptxt); _alt.attach(_body); msg.attach(_alt)
                else:
                    msg=MIMEMultipart('alternative'); msg.attach(_ptxt); msg.attach(_body)
                _domain=u.split('@')[-1] if '@' in u else 'mail.com'
                msg['From']=f"{sname} <{u}>"; msg['To']=to_email
                msg['Subject']=data.get('subject','')
                msg['Date']=formatdate(localtime=True)
                msg['Message-ID']=make_msgid(domain=_domain)
                msg['MIME-Version']='1.0'
                msg['List-Unsubscribe']='<mailto:unsubscribe@%s?subject=unsubscribe>' % _domain
                msg['List-Unsubscribe-Post']='List-Unsubscribe=One-Click'
                msg['Precedence']='bulk'
                msg['X-Priority']='3'
                if att:
                    try:
                        import base64 as _b64; from email.mime.base import MIMEBase; from email import encoders as _enc
                        _ac=att['content']+'='*(-len(att['content'])%4)
                        _ap=MIMEBase(*(att.get('type','application/octet-stream')+'/x').split('/')[:2])
                        _ap.set_payload(_b64.b64decode(_ac)); _enc.encode_base64(_ap)
                        _ap.add_header('Content-Disposition','attachment',filename=att.get('name','attachment'))
                        msg.attach(_ap)
                    except Exception as _ae: logging.warning(f'Attach err: {_ae}')
                with smtplib.SMTP(srv,port,timeout=30) as s:
                    s.ehlo(); s.starttls(); s.ehlo(); s.login(u,p); s.send_message(msg)
                logging.info(f"Sent to {to_email}")
                self.send_response(200); self.send_header('Content-type','application/json'); self.end_headers()
                self.wfile.write(json.dumps({'success':True,'message':'Email sent'}).encode())
            except Exception as e:
                logging.error(str(e))
                self.send_response(500); self.send_header('Content-type','application/json'); self.end_headers()
                self.wfile.write(json.dumps({'success':False,'error':str(e)}).encode())
        else: self.send_response(404); self.end_headers()
if __name__ == '__main__':
    srv = HTTPServer(('0.0.0.0',3000), EmailRelayHandler)
    logging.info('Relay started on port 3000'); srv.serve_forever()
PYEOF

chmod +x /opt/email_relay_server.py

cat > /etc/systemd/system/email-relay.service << 'SVCEOF'
[Unit]
Description=KINGMAILER Email Relay
After=network.target
[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/email_relay_server.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable email-relay.service
systemctl restart email-relay.service
sleep 3
systemctl is-active email-relay.service && echo 'RELAY_OK' || echo 'RELAY_FAILED'
curl -s http://localhost:3000/health | head -c 200
"""

        response = ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={'commands': [setup_script]},
            Comment='KINGMAILER relay restart'
        )
        command_id = response['Command']['CommandId']

        # Poll for result (up to 45s)
        import time as _time
        for _ in range(9):
            _time.sleep(5)
            try:
                out = ssm_client.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
                status = out['Status']
                if status in ('Success', 'Failed', 'TimedOut', 'Cancelled'):
                    stdout = out.get('StandardOutputContent', '')
                    stderr = out.get('StandardErrorContent', '')
                    if 'RELAY_OK' in stdout:
                        return {'success': True, 'message': '✅ Relay server restarted successfully!', 'output': stdout[-500:]}
                    elif status == 'Success':
                        return {'success': True, 'message': 'SSM command completed — check health in 15 seconds', 'output': stdout[-500:]}
                    else:
                        return {'success': False, 'error': f'Command {status}: {stderr[-300:] or stdout[-300:]}'}
            except Exception:
                continue

        return {'success': True, 'message': '⏳ Restart command sent — check health in 30 seconds', 'command_id': command_id}

    except Exception as e:
        err = str(e)
        is_ssm_unregistered = ('InvalidInstanceId' in err or 'not registered' in err.lower()
                               or 'ManagedInstance' in err or 'isManagedInstance' in err)
        if is_ssm_unregistered:
            # Auto-attach SSM IAM role so next click works
            attach = _attach_ssm_role(access_key, secret_key, region, instance_id)
            if attach.get('attached'):
                return {
                    'success': False,
                    'ssm_role_attached': True,
                    'message': '🔑 SSM role attached to instance. Wait 60 seconds for SSM to register, then click Restart Relay again.'
                }
            elif attach.get('already_had_profile'):
                return {
                    'success': False,
                    'ssm_not_available': True,
                    'message': '⚠️ SSM agent not responding (instance has IAM role but SSM agent may not be installed). Terminate this instance and create a new one — the new setup is hardened and will work.'
                }
            else:
                return {
                    'success': False,
                    'ssm_not_available': True,
                    'message': f'⚠️ Could not attach SSM role: {attach.get("error")}. Terminate this instance and create a new one.'
                }
        return {'success': False, 'error': f'SSM error: {err}'}


def _attach_ssm_role(access_key, secret_key, region, instance_id):
    """Attach AmazonSSMManagedInstanceCore IAM role to enable SSM on an instance."""
    import time as _t
    try:
        iam = boto3.client('iam', aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        ec2 = boto3.client('ec2', region_name=region, aws_access_key_id=access_key, aws_secret_access_key=secret_key)

        role_name = 'KINGMAILER-SSM-Role'
        profile_name = 'KINGMAILER-SSM-Profile'
        ssm_policy_arn = 'arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore'

        # Check if instance already has a profile
        existing = ec2.describe_iam_instance_profile_associations(
            Filters=[{'Name': 'instance-id', 'Values': [instance_id]}]
        )
        if existing['IamInstanceProfileAssociations']:
            return {'attached': False, 'already_had_profile': True}

        # Create role if not exists
        trust = json.dumps({
            'Version': '2012-10-17',
            'Statement': [{'Effect': 'Allow', 'Principal': {'Service': 'ec2.amazonaws.com'}, 'Action': 'sts:AssumeRole'}]
        })
        try:
            iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=trust,
                            Description='KINGMAILER EC2 SSM access role')
        except iam.exceptions.EntityAlreadyExistsException:
            pass

        # Attach SSM policy
        try:
            iam.attach_role_policy(RoleName=role_name, PolicyArn=ssm_policy_arn)
        except Exception:
            pass

        # Create instance profile
        try:
            iam.create_instance_profile(InstanceProfileName=profile_name)
            _t.sleep(3)
            iam.add_role_to_instance_profile(InstanceProfileName=profile_name, RoleName=role_name)
            _t.sleep(5)
        except iam.exceptions.EntityAlreadyExistsException:
            pass

        # Get profile ARN
        profile = iam.get_instance_profile(InstanceProfileName=profile_name)
        profile_arn = profile['InstanceProfile']['Arn']

        # Attach to instance
        ec2.associate_iam_instance_profile(
            IamInstanceProfile={'Arn': profile_arn},
            InstanceId=instance_id
        )
        return {'attached': True}

    except Exception as e:
        return {'attached': False, 'error': str(e)}


def fix_relay_instance(access_key, secret_key, region, instance_id):
    """Stop instance, replace UserData with a #cloud-boothook relay script, start it.
    This repairs broken instances where the original UserData never ran properly."""
    import base64 as _b64
    try:
        ec2 = boto3.client(
            'ec2', region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

        # Check current state
        desc = ec2.describe_instances(InstanceIds=[instance_id])
        state = desc['Reservations'][0]['Instances'][0]['State']['Name']

        if state in ('terminated', 'shutting-down'):
            return {'success': False, 'error': f'Instance is {state} and cannot be fixed — please terminate and create a new one.'}

        # Stop if running or stopping
        if state == 'running':
            ec2.stop_instances(InstanceIds=[instance_id])
        if state in ('running', 'stopping'):
            waiter = ec2.get_waiter('instance_stopped')
            waiter.wait(InstanceIds=[instance_id], WaiterConfig={'Delay': 15, 'MaxAttempts': 24})

        # New UserData: #cloud-boothook runs on EVERY boot, bypasses cloud-init "already ran" cache
        new_userdata = r"""#cloud-boothook
#!/bin/bash
exec > /var/log/boothook.log 2>&1
echo "=== KINGMAILER Relay BootHook $(date) ==="
which python3 || yum install -y python3 2>/dev/null || dnf install -y python3 2>/dev/null || true
mkdir -p /opt

cat > /opt/email_relay_server.py << 'PYEOF'
#!/usr/bin/env python3
import json, re, smtplib, logging, socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
from datetime import datetime
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.FileHandler('/var/log/email_relay.log'), logging.StreamHandler()])
class EmailRelayHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a): logging.info("%s - %s" % (self.client_address[0], fmt%a))
    def do_GET(self):
        if self.path in ('/', '/health'):
            self.send_response(200); self.send_header('Content-type','application/json'); self.end_headers()
            def chk(p):
                try:
                    s=socket.socket(); s.settimeout(3); r=s.connect_ex(('smtp.gmail.com',p)); s.close(); return 'open' if r==0 else 'blocked'
                except: return 'unknown'
            self.wfile.write(json.dumps({'status':'healthy','service':'KINGMAILER Relay',
                'timestamp':datetime.now().isoformat(),'port_587_outbound':chk(587),'port_465_outbound':chk(465)}).encode())
        else: self.send_response(404); self.end_headers()
    def do_POST(self):
        if self.path == '/relay':
            try:
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])).decode())
                smtp_config = data.get('smtp_config')
                if not smtp_config: raise ValueError('SMTP config required')
                to_email = data.get('to','')
                if not to_email: raise ValueError('Recipient required')
                provider = smtp_config.get('provider','gmail')
                u = smtp_config.get('user'); p = smtp_config.get('pass')
                if not u or not p: raise ValueError('SMTP credentials required')
                sname = smtp_config.get('sender_name', data.get('from_name','KINGMAILER'))
                if provider=='gmail': srv,port='smtp.gmail.com',587
                elif provider in ('outlook','hotmail'): srv,port='smtp-mail.outlook.com',587
                else: srv,port=smtp_config.get('host','smtp.gmail.com'),int(smtp_config.get('port',587))
                att=data.get('attachment')
                _html=data.get('html','')
                _plain=data.get('plain','') or re.sub('<[^>]+',' ',_html)
                _body=MIMEText(_html,'html','utf-8'); _ptxt=MIMEText(_plain,'plain','utf-8')
                if att:
                    msg=MIMEMultipart('mixed'); _alt=MIMEMultipart('alternative'); _alt.attach(_ptxt); _alt.attach(_body); msg.attach(_alt)
                else:
                    msg=MIMEMultipart('alternative'); msg.attach(_ptxt); msg.attach(_body)
                _domain=u.split('@')[-1] if '@' in u else 'mail.com'
                msg['From']="%s <%s>" % (sname,u); msg['To']=to_email; msg['Subject']=data.get('subject','')
                msg['Date']=formatdate(localtime=True)
                msg['Message-ID']=make_msgid(domain=_domain)
                msg['MIME-Version']='1.0'
                msg['List-Unsubscribe']='<mailto:unsubscribe@%s?subject=unsubscribe>' % _domain
                msg['List-Unsubscribe-Post']='List-Unsubscribe=One-Click'
                msg['Precedence']='bulk'
                msg['X-Priority']='3'
                if att:
                    try:
                        import base64 as _b64; from email.mime.base import MIMEBase; from email import encoders as _enc
                        _ac=att['content']+'='*(-len(att['content'])%4)
                        _ap=MIMEBase(*(att.get('type','application/octet-stream')+'/x').split('/')[:2])
                        _ap.set_payload(_b64.b64decode(_ac)); _enc.encode_base64(_ap)
                        _ap.add_header('Content-Disposition','attachment',filename=att.get('name','attachment'))
                        msg.attach(_ap)
                    except Exception as _ae: logging.warning("Attach err: %s" % _ae)
                with smtplib.SMTP(srv,port,timeout=30) as s:
                    s.ehlo(); s.starttls(); s.ehlo(); s.login(u,p); s.send_message(msg)
                logging.info("Sent to %s" % to_email)
                self.send_response(200); self.send_header('Content-type','application/json'); self.end_headers()
                self.wfile.write(json.dumps({'success':True,'message':'Email sent'}).encode())
            except Exception as e:
                logging.error(str(e))
                self.send_response(500); self.send_header('Content-type','application/json'); self.end_headers()
                self.wfile.write(json.dumps({'success':False,'error':str(e)}).encode())
        else: self.send_response(404); self.end_headers()
if __name__ == '__main__':
    srv = HTTPServer(('0.0.0.0',3000), EmailRelayHandler)
    logging.info('Relay started on port 3000'); srv.serve_forever()
PYEOF

chmod +x /opt/email_relay_server.py

cat > /etc/systemd/system/email-relay.service << 'SVCEOF'
[Unit]
Description=KINGMAILER Email Relay
After=network.target
[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/email_relay_server.py
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable email-relay.service
systemctl restart email-relay.service
echo '* * * * * root systemctl is-active email-relay || systemctl restart email-relay' > /etc/cron.d/email-relay-watchdog
echo "=== Relay BootHook Done $(date) ==="
"""

        encoded = _b64.b64encode(new_userdata.encode('utf-8')).decode('utf-8')
        ec2.modify_instance_attribute(
            InstanceId=instance_id,
            UserData={'Value': encoded}
        )

        # Start the instance
        ec2.start_instances(InstanceIds=[instance_id])

        return {
            'success': True,
            'message': '✅ Instance is restarting with a fresh relay setup (#cloud-boothook). '
                       'The relay will auto-install on every boot. Check health in 3-5 minutes.'
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


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
            
            elif action == 'restart_relay':
                instance_id = data.get('instance_id')
                if not instance_id:
                    result = {'success': False, 'error': 'instance_id required'}
                elif not AWS_CREDENTIALS:
                    result = {'success': False, 'error': 'AWS credentials not configured'}
                else:
                    result = restart_relay_via_ssm(
                        AWS_CREDENTIALS['access_key'],
                        AWS_CREDENTIALS['secret_key'],
                        AWS_CREDENTIALS['region'],
                        instance_id
                    )

            elif action == 'fix_relay':
                instance_id = data.get('instance_id')
                if not instance_id:
                    result = {'success': False, 'error': 'instance_id required'}
                elif not AWS_CREDENTIALS:
                    result = {'success': False, 'error': 'AWS credentials not configured'}
                else:
                    result = fix_relay_instance(
                        AWS_CREDENTIALS['access_key'],
                        AWS_CREDENTIALS['secret_key'],
                        AWS_CREDENTIALS['region'],
                        instance_id
                    )

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
