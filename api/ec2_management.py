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
import base64 as _b64

# In-memory storage for EC2 instances and credentials
EC2_INSTANCES = []
AWS_CREDENTIALS = None

# ── Relay server script (base64-encoded at import time, injected into UserData) ──
# Using string concatenation (no f-strings, no heredocs) avoids ALL escaping issues
_RELAY_SCRIPT = (
    '#!/usr/bin/env python3\n'
    '# KINGMAILER Relay v10.0 — JetMailer Style (SMTP + Gmail API via EC2 IP)\n'
    '# How it works: Vercel builds the full MIME message, sends it here.\n'
    '# This relay authenticates to your SMTP provider (Gmail/Outlook/etc) on port 587\n'
    '# from the EC2 IP — so the EC2 IP appears in email headers.\n'
    '# NO port 25 needed. Works immediately after EC2 creation.\n'
    'import json,re,smtplib,logging,socket,base64,os,uuid,urllib.request,urllib.parse,urllib.error\n'
    'from http.server import HTTPServer,BaseHTTPRequestHandler\n'
    'from email.mime.text import MIMEText\n'
    'from email.mime.multipart import MIMEMultipart\n'
    'from email.mime.base import MIMEBase\n'
    'from email import encoders\n'
    'from email.utils import formatdate,make_msgid\n'
    'from datetime import datetime\n'
    'logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s",\n'
    ' handlers=[logging.FileHandler("/var/log/email_relay.log"),logging.StreamHandler()])\n'
    '\n'
    'def _smtp_connect(sm):\n'
    ' """Return (server, port) tuple from smtp_config dict."""\n'
    ' pv=sm.get("provider","gmail").lower()\n'
    ' if pv=="gmail":return "smtp.gmail.com",587\n'
    ' if pv in("outlook","hotmail","microsoft","live"):return "smtp-mail.outlook.com",587\n'
    ' if pv=="yahoo":return "smtp.mail.yahoo.com",587\n'
    ' if pv=="zoho":return "smtp.zoho.com",587\n'
    ' if pv in("brevo","sendinblue"):return "smtp-relay.brevo.com",587\n'
    ' if pv=="sendgrid":return "smtp.sendgrid.net",587\n'
    ' return sm.get("host","smtp.gmail.com"),int(sm.get("port",587))\n'
    '\n'
    'def _port_status(p):\n'
    ' try:\n'
    '  s=socket.socket();s.settimeout(3);r=s.connect_ex(("smtp.gmail.com",p));s.close()\n'
    '  return "open" if r==0 else "blocked"\n'
    ' except:return "unknown"\n'
    '\n'
    'def _relay_public_ip():\n'
    ' try:\n'
    '  req=urllib.request.Request("http://169.254.169.254/latest/meta-data/public-ipv4",method="GET")\n'
    '  with urllib.request.urlopen(req,timeout=2) as resp:\n'
    '   return resp.read().decode("utf-8").strip()\n'
    ' except:return "unknown"\n'
    '\n'
    'class R(BaseHTTPRequestHandler):\n'
    ' def log_message(self,f,*a):logging.info("%s %s"%(self.client_address[0],f%a))\n'
    ' def do_GET(self):\n'
    '  if self.path in("/","/health"):\n'
    '   self.send_response(200);self.send_header("Content-type","application/json");self.end_headers()\n'
    '   self.wfile.write(json.dumps({"status":"healthy","service":"KINGMAILER Relay v10.0","timestamp":datetime.now().isoformat(),"port_587":_port_status(587),"port_465":_port_status(465),"mode":"smtp-or-gmail-api-via-ec2-ip","note":"JetMailer style - no port 25 needed","supports":["raw","gmail_api"],"relay_public_ip":_relay_public_ip()}).encode())\n'
    '  else:self.send_response(404);self.end_headers()\n'
    '\n'
    ' def do_POST(self):\n'
    '  if self.path=="/relay":\n'
    '   try:\n'
    '    d=json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode())\n'
    '    tp=d.get("type","")\n'
    '\n'
    '    # ── GMAIL API MODE: send through Gmail SMTP XOAUTH2 from EC2 host ───\n'
    '    if tp=="gmail_api":\n'
    '     gc=d.get("gmail_config") or {}\n'
    '     if not gc:raise ValueError("Gmail config required for gmail_api mode")\n'
    '     gu=gc.get("user","")\n'
    '     at=gc.get("access_token","")\n'
    '     if not gu:raise ValueError("gmail_config.user missing")\n'
    '     if not at:raise ValueError("gmail_config.access_token missing")\n'
    '     rb=d.get("raw_email","")\n'
    '     fa=d.get("from_addr",gu)\n'
    '     ta=d.get("to_addr","")\n'
    '     if not rb:raise ValueError("raw_email required for gmail_api mode")\n'
    '     if not ta:raise ValueError("to_addr required for gmail_api mode")\n'
    '     try:\n'
    '      raw=base64.b64decode(rb+"="*(-len(rb)%4))\n'
    '     except Exception as _be:\n'
    '      raise ValueError("Invalid raw_email base64 payload: %s"%str(_be))\n'
    '\n'
    '     def _auth_xoauth2(smtp, user, token):\n'
    '      astr="user=%s\\x01auth=Bearer %s\\x01\\x01"%(user,token)\n'
    '      enc=base64.b64encode(astr.encode("utf-8")).decode("ascii")\n'
    '      code,resp=smtp.docmd("AUTH","XOAUTH2 "+enc)\n'
    '      if code != 235:\n'
    '       raise ValueError("XOAUTH2 auth failed: %s %s"%(code,resp.decode("utf-8","ignore") if isinstance(resp,bytes) else str(resp)))\n'
    '\n'
    '     def _send_gmail(token):\n'
    '      dm=gu.split("@")[-1] if "@" in gu else "relay.local"\n'
    '      with smtplib.SMTP("smtp.gmail.com",587,timeout=30,local_hostname=dm) as s:\n'
    '       s.ehlo();s.starttls();s.ehlo()\n'
    '       _auth_xoauth2(s,gu,token)\n'
    '       s.sendmail(fa,[ta],raw)\n'
    '      return {"id":"smtp-xoauth2"}\n'
    '\n'
    '     def _send_gmail_api(token):\n'
    '      graw=base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")\n'
    '      gurl="https://gmail.googleapis.com/gmail/v1/users/me/messages/send"\n'
    '      body=json.dumps({"raw":graw}).encode("utf-8")\n'
    '      req=urllib.request.Request(gurl,data=body,method="POST")\n'
    '      req.add_header("Authorization","Bearer %s"%token)\n'
    '      req.add_header("Content-Type","application/json")\n'
    '      with urllib.request.urlopen(req,timeout=30) as resp:\n'
    '       return json.loads(resp.read().decode("utf-8"))\n'
    '\n'
    '     def _refresh_token(cfg):\n'
    '      rt=cfg.get("refresh_token","")\n'
    '      cid=cfg.get("client_id","")\n'
    '      csec=cfg.get("client_secret","")\n'
    '      if not rt or not cid or not csec:return None\n'
    '      turl="https://oauth2.googleapis.com/token"\n'
    '      p={"refresh_token":rt,"client_id":cid,"client_secret":csec,"grant_type":"refresh_token"}\n'
    '      data=urllib.parse.urlencode(p).encode("utf-8")\n'
    '      req=urllib.request.Request(turl,data=data,method="POST")\n'
    '      req.add_header("Content-Type","application/x-www-form-urlencoded")\n'
    '      try:\n'
    '       with urllib.request.urlopen(req,timeout=20) as resp:\n'
    '        out=json.loads(resp.read().decode("utf-8"))\n'
    '        return out.get("access_token")\n'
    '      except Exception:\n'
    '       return None\n'
    '\n'
    '     try:\n'
    '      rj=_send_gmail(at)\n'
    '      self.send_response(200);self.send_header("Content-type","application/json");self.end_headers()\n'
    '      self.wfile.write(json.dumps({"success":True,"message":"Email sent via EC2 relay using Gmail SMTP XOAUTH2","gmail_msg_id":rj.get("id","")}).encode())\n'
    '      return\n'
    '     except Exception as he:\n'
    '      em=str(he)\n'
    '      if ("XOAUTH2" in em or "535" in em or "Invalid credentials" in em or "5.7.8" in em):\n'
    '       nat=_refresh_token(gc)\n'
    '       if nat:\n'
    '        try:\n'
    '         rj=_send_gmail(nat)\n'
    '         self.send_response(200);self.send_header("Content-type","application/json");self.end_headers()\n'
    '         self.wfile.write(json.dumps({"success":True,"message":"Email sent via EC2 relay using Gmail SMTP XOAUTH2 (token refreshed)","gmail_msg_id":rj.get("id","")}).encode())\n'
    '         return\n'
    '        except Exception as he2:\n'
    '         try:\n'
    '          rj=_send_gmail_api(nat)\n'
    '          self.send_response(200);self.send_header("Content-type","application/json");self.end_headers()\n'
    '          self.wfile.write(json.dumps({"success":True,"message":"Email sent via EC2 relay fallback using Gmail API (reauth with https://mail.google.com/ scope to restore SMTP-IP path)","gmail_msg_id":rj.get("id","")}).encode())\n'
    '          return\n'
    '         except Exception as he3:\n'
    '          raise ValueError("Gmail SMTP XOAUTH2 failed after refresh: %s | Gmail API fallback failed: %s"%(str(he2),str(he3)))\n'
    '      try:\n'
    '       rj=_send_gmail_api(at)\n'
    '       self.send_response(200);self.send_header("Content-type","application/json");self.end_headers()\n'
    '       self.wfile.write(json.dumps({"success":True,"message":"Email sent via EC2 relay fallback using Gmail API (reauth with https://mail.google.com/ scope to restore SMTP-IP path)","gmail_msg_id":rj.get("id","")}).encode())\n'
    '       return\n'
    '      except Exception:\n'
    '       pass\n'
    '      raise ValueError("Gmail SMTP XOAUTH2 failed: %s"%em)\n'

    '    sm=d.get("smtp_config")\n'
    '    if not sm:raise ValueError("SMTP config required — add SMTP accounts in the SMTP Config tab")\n'
    '    u=sm.get("user","");p=sm.get("pass","")\n'
    '    if not u:raise ValueError("SMTP username missing in config")\n'
    '    if not p:raise ValueError("SMTP password/app-password missing in config")\n'
    '    srv,port=_smtp_connect(sm)\n'
    '    dm=u.split("@")[-1] if "@" in u else "relay.local"\n'
    '\n'
    '    # ── PRIMARY: raw pre-built MIME path (Vercel builds full msg) ───────\n'
    '    if d.get("type")=="raw":\n'
    '     raw=base64.b64decode(d["raw_email"]+"="*(-len(d["raw_email"])%4))\n'
    '     fa=d.get("from_addr",u);ta=d.get("to_addr","")\n'
    '     if not ta:raise ValueError("to_addr required for raw mode")\n'
    '     with smtplib.SMTP(srv,port,timeout=30,local_hostname=dm) as s:\n'
    '      s.ehlo();s.starttls();s.ehlo();s.login(u,p)\n'
    '      s.sendmail(fa,[ta],raw)\n'
    '     logging.info("RAW sent to %s via %s:%d (EC2 IP in headers)"%(ta,srv,port))\n'
    '     self.send_response(200);self.send_header("Content-type","application/json");self.end_headers()\n'
    '     self.wfile.write(json.dumps({"success":True,"message":"Email sent via EC2 relay (JetMailer style - authenticated SMTP from EC2 IP)"}).encode())\n'
    '     return\n'
    '\n'
    '    # ── LEGACY: JSON path (backward compat for old relay callers) ───────\n'
    '    to=d.get("to","");subj=d.get("subject","");htm=d.get("html","");att=d.get("attachment")\n'
    '    if not to:raise ValueError("Recipient required")\n'
    '    sn=d.get("from_name") or sm.get("sender_name","")\n'
    '    try:sn.encode("ascii")\n'
    '    except:import email.header as _eh;sn=_eh.Header(sn,"utf-8").encode()\n'
    '    jr="<!-- mid:"+uuid.uuid4().hex[:8]+" -->\\n"\n'
    '    htm=(htm.replace("</body>",jr+"</body>") if "</body>" in htm else htm+jr)\n'
    '    pl=re.sub(r"<br\\s*/?>","\\n",htm,flags=re.IGNORECASE)\n'
    '    pl=re.sub(r"<p[^>]*>","\\n",pl,flags=re.IGNORECASE)\n'
    '    pl=re.sub(r"<[^>]+>","",pl)\n'
    '    pl=re.sub(r"[ \\t]+"," ",pl).strip()\n'
    '    fh="%s <%s>"%(sn,u) if sn else u\n'
    '    if att:\n'
    '     msg=MIMEMultipart("mixed");alt=MIMEMultipart("alternative")\n'
    '     _tp=MIMEText(pl,"plain","utf-8");_th=MIMEText(htm,"html","utf-8")\n'
    '     for _p in [_tp,_th]:\n'
    '      if "MIME-Version" in _p:del _p["MIME-Version"]\n'
    '     alt.attach(_tp);alt.attach(_th)\n'
    '     if "MIME-Version" in alt:del alt["MIME-Version"]\n'
    '     msg.attach(alt)\n'
    '    else:\n'
    '     msg=MIMEMultipart("alternative")\n'
    '     _tp=MIMEText(pl,"plain","utf-8");_th=MIMEText(htm,"html","utf-8")\n'
    '     for _p in [_tp,_th]:\n'
    '      if "MIME-Version" in _p:del _p["MIME-Version"]\n'
    '     msg.attach(_tp);msg.attach(_th)\n'
    '    msg["From"]=fh;msg["To"]=to;msg["Subject"]=subj\n'
    '    msg["Date"]=formatdate(localtime=True);msg["Message-ID"]=make_msgid(domain=dm)\n'
    '    msg["Reply-To"]=fh\n'
    '    _fe=re.search(r"<(.+?)>",fh);_fe=_fe.group(1) if _fe else fh\n'
    '    msg["List-Unsubscribe"]="<mailto:"+_fe+"?subject=unsubscribe>"\n'
    '    if att:\n'
    '     try:\n'
    '      ac=att["content"]+"="*(-len(att["content"])%4)\n'
    '      fd=base64.b64decode(ac);nm=att.get("name","attachment");mt=att.get("type","application/octet-stream")\n'
    '      mn,sb=mt.split("/",1) if "/" in mt else ("application","octet-stream")\n'
    '      ap=MIMEBase(mn,sb);ap.set_param("name",nm);ap.set_payload(fd);encoders.encode_base64(ap)\n'
    '      ap.add_header("Content-Disposition","attachment",filename=nm)\n'
    '      if "MIME-Version" in ap:del ap["MIME-Version"]\n'
    '      msg.attach(ap)\n'
    '     except Exception as ae:logging.warning("Attach err: %s"%ae)\n'
    '    with smtplib.SMTP(srv,port,timeout=30,local_hostname=dm) as s:\n'
    '     s.ehlo();s.starttls();s.ehlo();s.login(u,p);s.send_message(msg)\n'
    '    logging.info("LEGACY sent to %s via %s:%d"%(to,srv,port))\n'
    '    self.send_response(200);self.send_header("Content-type","application/json");self.end_headers()\n'
    '    self.wfile.write(json.dumps({"success":True,"message":"Email sent via EC2 relay"}).encode())\n'
    '   except Exception as e:\n'
    '    logging.error("RELAY ERROR: %s"%str(e))\n'
    '    self.send_response(500);self.send_header("Content-type","application/json");self.end_headers()\n'
    '    self.wfile.write(json.dumps({"success":False,"error":str(e)}).encode())\n'
    '  else:self.send_response(404);self.end_headers()\n'
    '\n'
    'if __name__=="__main__":\n'
    ' srv2=HTTPServer(("0.0.0.0",3000),R)\n'
    ' logging.info("KINGMAILER Relay v10.0 started on port 3000 (JetMailer style)")\n'
    ' srv2.serve_forever()\n'
)
_RELAY_B64 = _b64.b64encode(_RELAY_SCRIPT.encode('utf-8')).decode('ascii')


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
                'us-east-1':      'ami-0277155c3f0ab2930',
                'us-east-2':      'ami-0a5d7a8e4c04a7b6e',
                'us-west-1':      'ami-04e914639d0cca79c',
                'us-west-2':      'ami-0a7d051a1c4b54f65',
                'eu-west-1':      'ami-00385a401487aefa4',
                'eu-west-2':      'ami-02ac6b6b72b7ddfbd',
                'eu-west-3':      'ami-0c6e6c4d3c4e7c7c3',
                'eu-central-1':   'ami-04e601abe3e1a910f',
                'eu-north-1':     'ami-07e00e6e9c4fd6cce',
                'ap-southeast-1': 'ami-04677bdaa3c2b6e24',
                'ap-southeast-2': 'ami-00a54b0b9b44f4094',
                'ap-northeast-1': 'ami-092c3564a82a31df7',
                'ap-northeast-2': 'ami-09e70258ddbdf3c90',
                'ap-south-1':     'ami-0f58b397bc5c1f2e8',
                'ap-east-1':      'ami-0bfb6a7bb5e44cff4',
                'sa-east-1':      'ami-04e1b59f8a9e2aeb3',
                'ca-central-1':   'ami-0fb7b22f2bc24ac61',
                'me-south-1':     'ami-034a706a11d7f06d7',
            }
            return ami_map.get(ec2_client.meta.region_name, ami_map['us-east-1'])
        
        # Sort by creation date and get the latest
        images = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)
        return images[0]['ImageId']
    except Exception:
        # Fallback AMI map
        ami_map = {
            'us-east-1':      'ami-0277155c3f0ab2930',
            'us-east-2':      'ami-0a5d7a8e4c04a7b6e',
            'us-west-1':      'ami-04e914639d0cca79c',
            'us-west-2':      'ami-0a7d051a1c4b54f65',
            'eu-west-1':      'ami-00385a401487aefa4',
            'eu-west-2':      'ami-02ac6b6b72b7ddfbd',
            'eu-west-3':      'ami-0c6e6c4d3c4e7c7c3',
            'eu-central-1':   'ami-04e601abe3e1a910f',
            'eu-north-1':     'ami-07e00e6e9c4fd6cce',
            'ap-southeast-1': 'ami-04677bdaa3c2b6e24',
            'ap-southeast-2': 'ami-00a54b0b9b44f4094',
            'ap-northeast-1': 'ami-092c3564a82a31df7',
            'ap-northeast-2': 'ami-09e70258ddbdf3c90',
            'ap-south-1':     'ami-0f58b397bc5c1f2e8',
            'ap-east-1':      'ami-0bfb6a7bb5e44cff4',
            'sa-east-1':      'ami-04e1b59f8a9e2aeb3',
            'ca-central-1':   'ami-0fb7b22f2bc24ac61',
            'me-south-1':     'ami-034a706a11d7f06d7',
        }
        return ami_map.get(ec2_client.meta.region_name, ami_map['us-east-1'])


def _get_subnet_for_sg(ec2_client, security_group):
    """
    Given a security group ID, find the VPC it belongs to and return
    a suitable subnet ID from that same VPC.
    Prefers subnets that auto-assign public IPs; falls back to any available subnet.
    Returns None if lookup fails (caller will handle).
    """
    sg_details = ec2_client.describe_security_groups(GroupIds=[security_group])
    vpc_id = sg_details['SecurityGroups'][0].get('VpcId')
    if not vpc_id:
        return None

    subnets_resp = ec2_client.describe_subnets(
        Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]},
            {'Name': 'state', 'Values': ['available']}
        ]
    )
    subnets = subnets_resp.get('Subnets', [])
    if not subnets:
        return None

    # Prefer subnets with auto-assign public IP; fall back to any available
    public_subnets = [s for s in subnets if s.get('MapPublicIpOnLaunch')]
    return (public_subnets or subnets)[0]['SubnetId']


def repair_security_group(access_key, secret_key, region, security_group_id):
    """
    Force-repair a security group to ensure ALL required ports are open.
    This is idempotent - safe to call multiple times.
    Returns details of what was fixed.
    """
    try:
        ec2_client = boto3.client(
            'ec2',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        # Required ports for KINGMAILER relay
        required_ports = [
            {'port': 3000, 'desc': 'Relay Server (CRITICAL)'},
            {'port': 587, 'desc': 'SMTP TLS'},
            {'port': 465, 'desc': 'SMTP SSL'},
            {'port': 25, 'desc': 'SMTP'},
            {'port': 22, 'desc': 'SSH'}
        ]
        
        added_ports = []
        already_open = []
        
        for port_info in required_ports:
            port = port_info['port']
            try:
                ec2_client.authorize_security_group_ingress(
                    GroupId=security_group_id,
                    IpPermissions=[{
                        'IpProtocol': 'tcp',
                        'FromPort': port,
                        'ToPort': port,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': f'KINGMAILER {port_info["desc"]}'}]
                    }]
                )
                added_ports.append(f"{port} ({port_info['desc']})")
            except ClientError as e:
                if 'InvalidPermission.Duplicate' in str(e):
                    already_open.append(f"{port} ({port_info['desc']})")
                else:
                    # Unexpected error - still record it
                    added_ports.append(f"{port} - ERROR: {str(e)[:50]}")
        
        message = ''
        if added_ports:
            message += f"✅ Opened ports: {', '.join(added_ports)}. "
        if already_open:
            message += f"ℹ️ Already open: {', '.join(already_open)}. "
        if not added_ports and not already_open:
            message = '⚠️ Could not verify ports (check AWS permissions)'
        
        return {
            'success': True,
            'security_group_id': security_group_id,
            'message': message.strip(),
            'ports_opened': len(added_ports),
            'ports_already_open': len(already_open)
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': f'Failed to repair security group: {str(e)}'
        }


def create_ec2_instance(access_key, secret_key, region, keypair_name, security_group=None):
    """Create a new EC2 instance for email sending.
    
    ROOT-CAUSE FIXES (v7.0):
    1. Always creates a FRESH dedicated security group (guaranteed ports open)
    2. Relay script is base64-encoded in UserData (no heredoc escaping issues)
    3. Simple bash without process substitution (works on all AMIs)
    """
    relay_b64 = _RELAY_B64  # use module-level pre-computed b64

    try:
        ec2_client = boto3.client(
            'ec2',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        # Get the latest Amazon Linux 2 AMI for the region
        ami_id = get_latest_amazon_linux_ami(ec2_client)

        # ── Determine target VPC ───────────────────────────────────────────────
        # If user supplied an SG, find its VPC so we create in the same VPC.
        # If no SG supplied, we'll create in the default VPC.
        target_vpc_id = None
        if security_group:
            try:
                sg_info = ec2_client.describe_security_groups(GroupIds=[security_group])
                target_vpc_id = sg_info['SecurityGroups'][0].get('VpcId')
            except Exception:
                pass  # Fall back to default VPC

        # ── ALWAYS create a FRESH dedicated security group ─────────────────────
        # This guarantees port 3000 is open. Never rely on the user's existing SG
        # because it may have been created before our port rules were added.
        new_sg_kwargs = dict(
            GroupName=f'kingmailer-relay-{int(time.time())}',
            Description='KINGMAILER Auto-Created Relay SG (port 3000 + SMTP)'
        )
        if target_vpc_id:
            new_sg_kwargs['VpcId'] = target_vpc_id

        fresh_sg = ec2_client.create_security_group(**new_sg_kwargs)
        instance_sg_id = fresh_sg['GroupId']

        ec2_client.authorize_security_group_ingress(
            GroupId=instance_sg_id,
            IpPermissions=[
                {'IpProtocol': 'tcp', 'FromPort': 3000, 'ToPort': 3000, 'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'KINGMAILER relay'}]},
                {'IpProtocol': 'tcp', 'FromPort': 587,  'ToPort': 587,  'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'SMTP TLS'}]},
                {'IpProtocol': 'tcp', 'FromPort': 465,  'ToPort': 465,  'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'SMTP SSL'}]},
                {'IpProtocol': 'tcp', 'FromPort': 25,   'ToPort': 25,   'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'SMTP'}]},
                {'IpProtocol': 'tcp', 'FromPort': 22,   'ToPort': 22,   'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'SSH'}]},
            ]
        )

        # ── Resolve subnet in the correct VPC ─────────────────────────────────
        subnet_id = None
        try:
            subnet_id = _get_subnet_for_sg(ec2_client, instance_sg_id)
        except Exception:
            pass

        # ── Build launch params ────────────────────────────────────────────────
        if subnet_id:
            network_interfaces = [{
                'DeviceIndex': 0,
                'SubnetId': subnet_id,
                'Groups': [instance_sg_id],
                'AssociatePublicIpAddress': True
            }]
            run_params = dict(
                ImageId=ami_id,
                InstanceType='t2.micro',
                KeyName=keypair_name,
                MinCount=1,
                MaxCount=1,
                NetworkInterfaces=network_interfaces,
            )
        else:
            run_params = dict(
                ImageId=ami_id,
                InstanceType='t2.micro',
                KeyName=keypair_name,
                MinCount=1,
                MaxCount=1,
                SecurityGroupIds=[instance_sg_id],
            )

        # ── UserData: write relay via base64 (NO heredoc quoting issues) ──────
        # relay_b64 was computed above from RELAY_SCRIPT string constant.
        # On the instance, we just: echo BASE64 | base64 -d > file
        user_data = f"""#!/bin/bash
exec >> /var/log/kingmailer-setup.log 2>&1
echo "=== KINGMAILER v9.1 Setup $(date) ==="

# 1. Ensure python3 is available
which python3 >/dev/null 2>&1 || yum install -y python3 >/dev/null 2>&1 || dnf install -y python3 >/dev/null 2>&1 || true
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null || echo /usr/bin/python3)
echo "Python: $PYTHON ($($PYTHON --version 2>&1))"

# 2. Disable OS-level firewall for port 3000 (AWS SG handles security)
setenforce 0 2>/dev/null || true
sed -i 's/SELINUX=enforcing/SELINUX=permissive/' /etc/selinux/config 2>/dev/null || true
iptables  -I INPUT -p tcp --dport 3000 -j ACCEPT 2>/dev/null || true
ip6tables -I INPUT -p tcp --dport 3000 -j ACCEPT 2>/dev/null || true
systemctl stop firewalld 2>/dev/null || true
systemctl disable firewalld 2>/dev/null || true

# 3. Decode and write relay server (base64-encoded - no quoting issues)
mkdir -p /opt
echo '{relay_b64}' | base64 -d > /opt/email_relay_server.py
chmod +x /opt/email_relay_server.py
echo "Relay script written: $(wc -l /opt/email_relay_server.py) lines"

# 4. Kill any old relay, start fresh immediately
pkill -f email_relay_server.py 2>/dev/null || true
sleep 1
nohup $PYTHON /opt/email_relay_server.py >> /var/log/email_relay.log 2>&1 &
RELAY_PID=$!
disown $RELAY_PID 2>/dev/null || true
echo "Relay started with PID: $RELAY_PID"

# 5. Verify after 3 seconds
sleep 3
if ss -tlnp 2>/dev/null | grep -q ':3000' || netstat -tlnp 2>/dev/null | grep ':3000'; then
    echo "SUCCESS: Relay listening on port 3000"
else
    echo "WARNING: Port 3000 not detected yet - may still be starting"
fi
curl -s --max-time 3 http://127.0.0.1:3000/health || echo "Health check pending"

# 6. Systemd service for auto-restart on reboot
cat > /etc/systemd/system/email-relay.service << 'SVCEOF'
[Unit]
Description=KINGMAILER Email Relay v9.1
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStartPre=/usr/sbin/iptables -I INPUT -p tcp --dport 3000 -j ACCEPT
ExecStart=/usr/bin/env python3 /opt/email_relay_server.py
Restart=always
RestartSec=5
KillMode=process

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable email-relay 2>/dev/null || true

# 7. Cron watchdog - restart relay if it dies
echo '* * * * * root pgrep -f email_relay_server.py >/dev/null 2>&1 || (iptables -I INPUT -p tcp --dport 3000 -j ACCEPT 2>/dev/null; nohup /usr/bin/env python3 /opt/email_relay_server.py >> /var/log/email_relay.log 2>&1 &)' > /etc/cron.d/kingmailer-watchdog
chmod 644 /etc/cron.d/kingmailer-watchdog

echo "=== Setup Complete $(date) ==="
"""

        response = ec2_client.run_instances(
            **run_params,
            UserData=user_data,
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': 'KINGMAILER-Email-Server'},
                    {'Key': 'Purpose', 'Value': 'Email Relay'},
                    {'Key': 'SG', 'Value': instance_sg_id}
                ]
            }]
        )
        
        instance_id = response['Instances'][0]['InstanceId']
        
        # Wait for instance to get public IP (NetworkInterfaces take longer)
        public_ip = 'Pending...'
        for attempt in range(12):  # Try for up to 60 seconds
            time.sleep(5)
            instances = ec2_client.describe_instances(InstanceIds=[instance_id])
            instance = instances['Reservations'][0]['Instances'][0]
            
            # Check both direct and NetworkInterface locations for public IP
            public_ip = instance.get('PublicIpAddress')
            if not public_ip and instance.get('NetworkInterfaces'):
                ni = instance['NetworkInterfaces'][0]
                if ni.get('Association'):
                    public_ip = ni['Association'].get('PublicIp')
            
            if public_ip:
                break

        if not public_ip:
            public_ip = 'Pending...'
        
        return {
            'success': True,
            'instance_id': instance_id,
            'public_ip': public_ip,
            'region': region,
            'state': instance['State']['Name'],
            'security_group_id': instance_sg_id,
            'setup_eta': '⏳ Relay will be ready in 2-3 minutes. Click "Check Health" to verify.'
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

        # Build the SSM script using base64 (same approach as UserData - no heredoc issues)
        relay_b64 = _RELAY_B64
        setup_script = f"""#!/bin/bash
exec >> /var/log/kingmailer-ssm-restart.log 2>&1
echo "=== KINGMAILER v7.0 Relay Restart via SSM $(date) ==="

# 1. Open OS firewall for port 3000
setenforce 0 2>/dev/null || true
iptables -I INPUT -p tcp --dport 3000 -j ACCEPT 2>/dev/null || true
systemctl stop firewalld 2>/dev/null || true

# 2. Find python3
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null || echo /usr/bin/python3)
echo "Python: $PYTHON"

# 3. Write relay using base64 decode (no heredoc = no quoting issues)
mkdir -p /opt
echo '{relay_b64}' | base64 -d > /opt/email_relay_server.py
chmod +x /opt/email_relay_server.py
echo "Relay script: $(wc -c /opt/email_relay_server.py) bytes"

# 4. Kill old relay, start fresh
pkill -f email_relay_server.py 2>/dev/null || true
sleep 1
nohup $PYTHON /opt/email_relay_server.py >> /var/log/email_relay.log 2>&1 &
disown $! 2>/dev/null || true
sleep 3

# 5. Check if relay is listening
if ss -tlnp 2>/dev/null | grep -q ':3000' || netstat -tlnp 2>/dev/null | grep ':3000'; then
    echo 'RELAY_OK'
else
    echo 'RELAY_STARTING'
fi
curl -s --max-time 3 http://127.0.0.1:3000/health || echo 'Health check pending'
echo "=== Restart Complete $(date) ===" """

        response = ssm_client.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={'commands': [setup_script]},
            Comment='KINGMAILER v7.0 relay restart'
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
                        return {'success': True, 'message': '✅ Relay server restarted successfully! Check health in 5 seconds.', 'output': stdout[-500:]}
                    elif status == 'Success':
                        return {'success': True, 'message': '✅ SSM command completed — check health in 15 seconds', 'output': stdout[-500:]}
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
                    'message': '⚠️ SSM agent not responding. Click "🔧 Fix Relay" button instead — it will stop/update/restart the instance with the new v7.0 relay.'
                }
            else:
                return {
                    'success': False,
                    'ssm_not_available': True,
                    'message': f'⚠️ Could not attach SSM role: {attach.get("error")}. Click "🔧 Fix Relay" button instead.'
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
    """Stop instance, replace UserData with the v7.0 base64-encoded relay script, start it.
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

        # New UserData: base64-encoded relay script — no heredoc quoting issues
        relay_b64 = _RELAY_B64
        new_userdata = f"""#!/bin/bash
exec >> /var/log/kingmailer-setup.log 2>&1
echo "=== KINGMAILER v7.0 Fix-Relay $(date) ==="

which python3 >/dev/null 2>&1 || yum install -y python3 >/dev/null 2>&1 || dnf install -y python3 >/dev/null 2>&1 || true
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null || echo /usr/bin/python3)

setenforce 0 2>/dev/null || true
iptables  -I INPUT -p tcp --dport 3000 -j ACCEPT 2>/dev/null || true
systemctl stop  firewalld 2>/dev/null || true
systemctl disable firewalld 2>/dev/null || true

mkdir -p /opt
echo '{relay_b64}' | base64 -d > /opt/email_relay_server.py
chmod +x /opt/email_relay_server.py

pkill -f email_relay_server.py 2>/dev/null || true
sleep 1

cat > /etc/systemd/system/email-relay.service << 'SVCEOF'
[Unit]
Description=KINGMAILER Email Relay
After=network.target
[Service]
Type=simple
User=root
ExecStart=/usr/bin/env python3 /opt/email_relay_server.py
Restart=always
RestartSec=5
StandardOutput=append:/var/log/email_relay.log
StandardError=append:/var/log/email_relay.log
[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable email-relay
systemctl restart email-relay
sleep 3
systemctl is-active email-relay || nohup $PYTHON /opt/email_relay_server.py >> /var/log/email_relay.log 2>&1 &

echo '* * * * * root systemctl is-active --quiet email-relay || systemctl restart email-relay' > /etc/cron.d/email-relay-watchdog
echo "=== Fix-Relay Done $(date) ==="
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
            'message': '✅ Instance is restarting with v7.0 relay setup (base64 encoded, no heredoc). '
                       'The relay starts automatically on boot. Check health in 3-5 minutes.'
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

def fix_security_group(access_key, secret_key, region, sg_id):
    """Force-adds all required ingress rules to a security group."""
    try:
        ec2 = boto3.client('ec2', region_name=region, aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {'IpProtocol': 'tcp', 'FromPort': 3000, 'ToPort': 3000, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 25, 'ToPort': 25, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 587, 'ToPort': 587, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 465, 'ToPort': 465, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
            ]
        )
        return {'success': True, 'message': f'✅ Security Group {sg_id} rules updated successfully! Port 3000 is now open.'}
    except ClientError as e:
        if 'InvalidPermission.Duplicate' in str(e):
            return {'success': True, 'message': f'ℹ️ Rules already exist for Security Group {sg_id}. If still unreachable, check AWS Network ACLs or Instance Firewall.'}
        return {'success': False, 'error': str(e)}
    except Exception as e:
        return {'success': False, 'error': str(e)}


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
            
            elif action == 'fix_sg':
                sg_id = data.get('security_group') or (AWS_CREDENTIALS.get('security_group') if AWS_CREDENTIALS else None)
                if not sg_id:
                    result = {'success': False, 'error': 'No Security Group ID provided or saved.'}
                elif not AWS_CREDENTIALS:
                    result = {'success': False, 'error': 'AWS credentials not configured'}
                else:
                    result = repair_security_group(
                        AWS_CREDENTIALS['access_key'],
                        AWS_CREDENTIALS['secret_key'],
                        AWS_CREDENTIALS['region'],
                        sg_id
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
