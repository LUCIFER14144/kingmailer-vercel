"""
KINGMAILER v4.0 - SMTP Sending API
Vercel Serverless Function for sending single emails via SMTP/SES/EC2
"""

from flask import Flask, request, jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import boto3
from botocore.exceptions import ClientError
import json
import os

app = Flask(__name__)

def send_via_smtp(smtp_config, to_email, subject, html_body, text_body=""):
    """Send email via SMTP (Gmail or custom server)"""
    try:
        # Determine if Gmail or custom SMTP
        is_gmail = smtp_config.get('provider') == 'gmail'
        
        if is_gmail:
            smtp_server = 'smtp.gmail.com'
            smtp_port = 587
        else:
            smtp_server = smtp_config.get('host', 'smtp.gmail.com')
            smtp_port = int(smtp_config.get('port', 587))
        
        smtp_user = smtp_config.get('user')
        smtp_pass = smtp_config.get('pass')
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Attach parts
        if text_body:
            msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send via SMTP
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        return {'success': True, 'message': f'Email sent via SMTP to {to_email}'}
    
    except smtplib.SMTPAuthenticationError:
        return {'success': False, 'error': 'SMTP authentication failed. Check your credentials.'}
    except smtplib.SMTPException as e:
        return {'success': False, 'error': f'SMTP error: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}


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
        
        return {'success': True, 'message': f'Email sent via SES to {to_email}', 'messageId': response['MessageId']}
    
    except ClientError as e:
        return {'success': False, 'error': f'SES error: {e.response["Error"]["Message"]}'}
    except Exception as e:
        return {'success': False, 'error': f'Unexpected error: {str(e)}'}


def send_via_ec2_relay(relay_url, to_email, subject, html_body, text_body=""):
    """Send email via EC2 relay endpoint"""
    try:
        import requests
        
        response = requests.post(
            relay_url,
            json={
                'to': to_email,
                'subject': subject,
                'html': html_body,
                'text': text_body
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return {'success': True, 'message': f'Email sent via EC2 relay to {to_email}'}
        else:
            return {'success': False, 'error': f'Relay returned status {response.status_code}'}
    
    except Exception as e:
        return {'success': False, 'error': f'EC2 relay error: {str(e)}'}


@app.route('/api/send', methods=['POST'])
def send_email():
    """Main endpoint for sending single emails"""
    try:
        data = request.get_json()
        
        # Extract parameters
        to_email = data.get('to')
        subject = data.get('subject', 'No Subject')
        html_body = data.get('html', '')
        text_body = data.get('text', '')
        send_method = data.get('method', 'smtp')
        
        # Validate
        if not to_email:
            return jsonify({'success': False, 'error': 'Recipient email is required'}), 400
        
        # Route based on send method
        if send_method == 'smtp' or send_method == 'gmail':
            smtp_config = data.get('smtp_config')
            if not smtp_config:
                return jsonify({'success': False, 'error': 'SMTP configuration is required'}), 400
            result = send_via_smtp(smtp_config, to_email, subject, html_body, text_body)
        
        elif send_method == 'ses':
            aws_config = data.get('aws_config')
            if not aws_config:
                return jsonify({'success': False, 'error': 'AWS SES configuration is required'}), 400
            result = send_via_ses(aws_config, to_email, subject, html_body, text_body)
        
        elif send_method == 'ec2':
            relay_url = data.get('relay_url')
            if not relay_url:
                return jsonify({'success': False, 'error': 'EC2 relay URL is required'}), 400
            result = send_via_ec2_relay(relay_url, to_email, subject, html_body, text_body)
        
        else:
            return jsonify({'success': False, 'error': f'Unknown send method: {send_method}'}), 400
        
        # Return result
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Server error: {str(e)}'}), 500


# Vercel serverless handler
def handler(request):
    with app.request_context(request.environ):
        return app.full_dispatch_request()
