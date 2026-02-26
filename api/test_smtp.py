"""
KINGMAILER v4.0 - SMTP Test API
Vercel Serverless Function for testing SMTP connections
"""

from flask import Flask, request, jsonify
import smtplib
import boto3
from botocore.exceptions import ClientError

app = Flask(__name__)

def test_smtp_connection(smtp_config):
    """Test SMTP connection and authentication"""
    try:
        is_gmail = smtp_config.get('provider') == 'gmail'
        
        if is_gmail:
            smtp_server = 'smtp.gmail.com'
            smtp_port = 587
        else:
            smtp_server = smtp_config.get('host')
            smtp_port = int(smtp_config.get('port', 587))
        
        smtp_user = smtp_config.get('user')
        smtp_pass = smtp_config.get('pass')
        
        # Test connection
        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
        
        return {
            'success': True,
            'message': f'✓ SMTP connection successful to {smtp_server}:{smtp_port}',
            'details': {
                'server': smtp_server,
                'port': smtp_port,
                'user': smtp_user,
                'tls': True
            }
        }
    
    except smtplib.SMTPAuthenticationError:
        return {
            'success': False,
            'error': 'Authentication failed. Check your username/password.',
            'fix': 'For Gmail, use App Password (not your regular password)'
        }
    except smtplib.SMTPConnectError as e:
        return {
            'success': False,
            'error': f'Cannot connect to SMTP server: {str(e)}',
            'fix': 'Check server address and port number'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Connection test failed: {str(e)}'
        }


def test_ses_connection(aws_config):
    """Test AWS SES connection"""
    try:
        ses_client = boto3.client(
            'ses',
            region_name=aws_config.get('region', 'us-east-1'),
            aws_access_key_id=aws_config.get('access_key'),
            aws_secret_access_key=aws_config.get('secret_key')
        )
        
        # Test by getting send quota
        quota = ses_client.get_send_quota()
        
        return {
            'success': True,
            'message': '✓ AWS SES connection successful',
            'details': {
                'quota': {
                    'max_24_hour': int(quota['Max24HourSend']),
                    'max_per_second': int(quota['MaxSendRate']),
                    'sent_last_24_hours': int(quota['SentLast24Hours'])
                }
            }
        }
    
    except ClientError as e:
        return {
            'success': False,
            'error': f'SES authentication failed: {e.response["Error"]["Message"]}',
            'fix': 'Check your AWS Access Key and Secret Key'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'SES test failed: {str(e)}'
        }


def test_ec2_relay(relay_url):
    """Test EC2 relay endpoint"""
    try:
        import requests
        
        response = requests.get(f"{relay_url}/health", timeout=5)
        
        if response.status_code == 200:
            return {
                'success': True,
                'message': '✓ EC2 relay is reachable',
                'details': {'url': relay_url, 'status': response.status_code}
            }
        else:
            return {
                'success': False,
                'error': f'Relay returned status {response.status_code}'
            }
    
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': 'Connection timeout. Check if EC2 instance is running.'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Cannot reach EC2 relay: {str(e)}'
        }


@app.route('/api/test_smtp', methods=['POST'])
def test_connection():
    """Test SMTP/SES/EC2 connection endpoint"""
    try:
        data = request.get_json()
        test_type = data.get('type', 'smtp')
        
        if test_type == 'smtp' or test_type == 'gmail':
            smtp_config = data.get('smtp_config')
            if not smtp_config:
                return jsonify({'success': False, 'error': 'SMTP configuration required'}), 400
            result = test_smtp_connection(smtp_config)
        
        elif test_type == 'ses':
            aws_config = data.get('aws_config')
            if not aws_config:
                return jsonify({'success': False, 'error': 'AWS configuration required'}), 400
            result = test_ses_connection(aws_config)
        
        elif test_type == 'ec2':
            relay_url = data.get('relay_url')
            if not relay_url:
                return jsonify({'success': False, 'error': 'Relay URL required'}), 400
            result = test_ec2_relay(relay_url)
        
        else:
            return jsonify({'success': False, 'error': f'Unknown test type: {test_type}'}), 400
        
        return jsonify(result), 200 if result['success'] else 400
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Test failed: {str(e)}'}), 500


# Vercel serverless handler
def handler(request):
    with app.request_context(request.environ):
        return app.full_dispatch_request()
