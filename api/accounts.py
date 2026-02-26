"""
KINGMAILER v4.0 - Account Management API  
Vercel Serverless Function for managing SMTP/SES accounts
"""

from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

# In-memory storage (for demo - use database in production)
ACCOUNTS_STORE = {
    'smtp_accounts': [],
    'ses_accounts': [],
    'ec2_relays': []
}

@app.route('/api/accounts', methods=['GET', 'POST', 'DELETE'])
def manage_accounts():
    """Manage email sending accounts"""
    try:
        if request.method == 'GET':
            # Return all accounts
            return jsonify({
                'success': True,
                'accounts': ACCOUNTS_STORE
            }), 200
        
        elif request.method == 'POST':
            # Add new account
            data = request.get_json()
            account_type = data.get('type')  # 'smtp', 'ses', 'ec2'
            
            if account_type == 'smtp':
                account = {
                    'id': len(ACCOUNTS_STORE['smtp_accounts']) + 1,
                    'provider': data.get('provider', 'gmail'),
                    'user': data.get('user'),
                    'pass': data.get('pass'),
                    'host': data.get('host'),
                    'port': data.get('port', 587),
                    'label': data.get('label', f"SMTP Account #{len(ACCOUNTS_STORE['smtp_accounts']) + 1}")
                }
                ACCOUNTS_STORE['smtp_accounts'].append(account)
                
                return jsonify({
                    'success': True,
                    'message': 'SMTP account added successfully',
                    'account': account
                }), 200
            
            elif account_type == 'ses':
                account = {
                    'id': len(ACCOUNTS_STORE['ses_accounts']) + 1,
                    'access_key': data.get('access_key'),
                    'secret_key': data.get('secret_key'),
                    'region': data.get('region', 'us-east-1'),
                    'from_email': data.get('from_email'),
                    'label': data.get('label', f"SES Account #{len(ACCOUNTS_STORE['ses_accounts']) + 1}")
                }
                ACCOUNTS_STORE['ses_accounts'].append(account)
                
                return jsonify({
                    'success': True,
                    'message': 'AWS SES account added successfully',
                    'account': account
                }), 200
            
            elif account_type == 'ec2':
                relay = {
                    'id': len(ACCOUNTS_STORE['ec2_relays']) + 1,
                    'url': data.get('url'),
                    'label': data.get('label', f"EC2 Relay #{len(ACCOUNTS_STORE['ec2_relays']) + 1}")
                }
                ACCOUNTS_STORE['ec2_relays'].append(relay)
                
                return jsonify({
                    'success': True,
                    'message': 'EC2 relay added successfully',
                    'relay': relay
                }), 200
            
            else:
                return jsonify({'success': False, 'error': 'Invalid account type'}), 400
        
        elif request.method == 'DELETE':
            # Delete account
            data = request.get_json()
            account_type = data.get('type')
            account_id = data.get('id')
            
            if account_type == 'smtp':
                ACCOUNTS_STORE['smtp_accounts'] = [
                    acc for acc in ACCOUNTS_STORE['smtp_accounts'] 
                    if acc['id'] != account_id
                ]
            elif account_type == 'ses':
                ACCOUNTS_STORE['ses_accounts'] = [
                    acc for acc in ACCOUNTS_STORE['ses_accounts'] 
                    if acc['id'] != account_id
                ]
            elif account_type == 'ec2':
                ACCOUNTS_STORE['ec2_relays'] = [
                    relay for relay in ACCOUNTS_STORE['ec2_relays'] 
                    if relay['id'] != account_id
                ]
            
            return jsonify({
                'success': True,
                'message': 'Account deleted successfully'
            }), 200
    
    except Exception as e:
        return jsonify({'success': False, 'error': f'Account management error: {str(e)}'}), 500


# Vercel serverless handler
def handler(request):
    with app.request_context(request.environ):
        return app.full_dispatch_request()
