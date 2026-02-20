MobileNumber = "7977386224"
comunication_type = "WhatsApp"
Email = "allrd.rooh@gmail.com"
source = "Customer 360"

import json
import requests
import os
import base64

ZOHO_CRM_BASE = "https://www.zohoapis.in/crm/v3"
WHATSAPP_BASE = "https://jio.allincall.in/campaign/external"
SMS_BASE = "https://jfl.jiocx.com/jfl/v1"


#main method 
def lambda_handler(event, context):
    try:
        # parse input -  to handle both API Gateway and direct calls
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            body = event
        
        # arguments (from zoho crm communication channels)
        RecordID = body.get('RecordID')
        Email = body.get('Email') 
        MobileNumber = body.get('MobileNumber', '')
        templateID = body.get('templateID')
        whatsappVariables = body.get('whatsappVariables', [])
        smsVariables = body.get('smsVariables', [])
        comuMode = body.get('comuMode', '')
        CCMSource = body.get('CCMSource', '')
        LAN = body.get('LAN', '')
        
        # if communication mode is 'sms', if not execute "whatsapp"
        isSendSMS = (comuMode.lower() == 'sms')
        
        print(f"RecordID={RecordID}, Email={Email}, Template={templateID}")
        print(f"Communication Mode={comuMode}, Source={CCMSource}, isSendSMS={isSendSMS}")
        
        # input validation
        if not RecordID or not Email or not templateID:
            return create_response(400, {"error": "Missing required parameters"})
        
        # get Zoho token from environment
        crm_token = os.environ.get('ZOHO_CRM_TOKEN', '1000.b09f6377a35ccc8700e448fa83630dd9.1df5c15625a52bdf3994d70981d12f89')
        
        # Step 1: Get mobile number if not provided 
        if not MobileNumber:
            MobileNumber = get_mobile_from_crm(Email, crm_token)
        
        if not MobileNumber:
            return create_response(400, {"error": "Mobile number not found"})
        
        # Step 2: Process WhatsApp 
        if not isSendSMS:  # whatsApp 
            whatsapp_template = get_whatsapp_template(templateID, crm_token)
            
            if not whatsapp_template:
                return create_response(400, {"error": "WhatsApp template not found"})
            
            payload_result = build_whatsapp_payload(whatsapp_template, MobileNumber, whatsappVariables)
            
            if not payload_result['success']:
                update_crm_record(RecordID, payload_result, crm_token)
                return create_response(400, {"error": payload_result['error']})
            
            send_result = send_whatsapp_message(payload_result['payload'])
            update_crm_record(RecordID, send_result, crm_token)
            
            return create_response(200, {
                "success": True,
                "record_id": RecordID,
                "status": send_result['status'],
                "message": "WhatsApp processed successfully"
            })
        
        # Step 3: Process SMS 
        else:
            sms_template = get_sms_template(templateID, crm_token)
            
            if not sms_template:
                update_sms_crm_record(RecordID, {"success": False, "error": "The SMS Template Not Found"}, crm_token)
                return create_response(400, {"error": "SMS template not found"})
            
            payload_result = build_sms_payload(sms_template, MobileNumber, smsVariables)
            
            if not payload_result['success']:
                update_sms_crm_record(RecordID, payload_result, crm_token)
                return create_response(400, {"error": payload_result['error']})
            
            send_result = send_sms_message(payload_result['payload'])
            update_sms_crm_record(RecordID, send_result, crm_token)
            
            return create_response(200, {
                "success": True,
                "record_id": RecordID,
                "status": send_result['status'],
                "message": "SMS processed successfully"
            })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return create_response(500, {"error": str(e)})
    
# serachRecords - contact number search 
def get_mobile_from_crm(email, crm_token):
    """
        searchContactsd2 = zoho.crm.searchRecords("Contacts","(Email:equals:" + Email + ")"); - python version
    """
    try:
        headers = {
            "Authorization": f"Zoho-oauthtoken {crm_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{ZOHO_CRM_BASE}/Contacts/search"
        params = {"criteria": f"(Email:equals:{email})"}
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                mobile = data['data'][0].get('Mobile')
                print(f"Found mobile for {email}: {mobile}")
                return mobile
        
        print(f"No mobile found for: {email}")
        return None
        
    except Exception as e:
        print(f"Error getting mobile: {e}")
        return None

# whatsapp template
def get_whatsapp_template(template_id, crm_token):
    """
       getWhatsappTemplate = zoho.crm.searchRecords("WhatsApp_Template","(Name:equals:" + templateID + ")"); - python version
    """
    try:
        headers = {
            "Authorization": f"Zoho-oauthtoken {crm_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{ZOHO_CRM_BASE}/WhatsApp_Template/search"
        params = {"criteria": f"(Name:equals:{template_id})"}
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                template = data['data'][0]
                print(f"Found template: {template_id}")
                return {
                    'Campaign_Id': template.get('Campaign_Id'),
                    'Client_Data_Name': template.get('Client_Data_Name'),
                    'whatsapp_bsp': template.get('whatsapp_bsp'),
                    'Dynamic_CTA': template.get('Dynamic_CTA'),
                    'Variable_Count': int(template.get('Variable_Count', 0))
                }
        
        print(f"Template not found: {template_id}")
        return None
        
    except Exception as e:
        print(f"Error getting template: {e}")
        return None

# sms template
def get_sms_template(template_id, crm_token):
    """
       getSmsTemplate = zoho.crm.searchRecords("SMS_Templates","(Name:equals:" + templateID + ")"); - python version
    """
    try:
        headers = {
            "Authorization": f"Zoho-oauthtoken {crm_token}",
            "Content-Type": "application/json"
        }
        
        url = f"{ZOHO_CRM_BASE}/SMS_Templates/search"
        params = {"criteria": f"(Name:equals:{template_id})"}
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                template = data['data'][0]
                print(f"Found SMS template: {template_id}")
                return {
                    'SMS_Header': template.get('SMS_Header'),
                    'SMS_Template_Content': template.get('SMS_Template_Content'),
                    'Template_ID': template.get('Template_ID')
                }
        
        print(f"SMS Template not found: {template_id}")
        return None
        
    except Exception as e:
        print(f"Error getting SMS template: {e}")
        return None

# whatsapp payload
def build_whatsapp_payload(template, mobile_number, variables):
    """
        Whatsapp payload including all the if/else conditions
    """
    try:
        campaignId = template.get('Campaign_Id')
        clientDataName = template.get('Client_Data_Name') 
        whatsappBsp = template.get('whatsapp_bsp')
        dynamicCta = template.get('Dynamic_CTA')
        whatsappVariableCount = template.get('Variable_Count', 0)
        
        # Base payload
        param_whatsapp = {
            "campaign_id": campaignId,
            "whatsapp_bsp": whatsappBsp,
            "client_data": {
                "phone_number": f"+91{mobile_number}",
                "name": clientDataName
            }
        }
        
        dynamicCtaValidate = "NA" if not dynamicCta else dynamicCta
        
        print(f"Template config: dynamicCta={dynamicCtaValidate}, variableCount={whatsappVariableCount}")
        print(f"Input variables: {variables}, count={len(variables)}")
        
        # Case 1: dynamicCtaValidate == "NA" && whatsappVariableCount != "0"
        if dynamicCtaValidate == "NA" and whatsappVariableCount != 0:
            if len(variables) == whatsappVariableCount + 1:
                # Last variable is dynamic CTA (Deluge case: variable count + 1)
                dynamic_data = {}
                for i, var in enumerate(variables[:-1], 1):
                    dynamic_data[f"key{i}"] = var
                
                param_whatsapp["client_data"]["dynamic_data"] = dynamic_data
                param_whatsapp["client_data"]["dynamic_cta"] = variables[-1]
                return {"success": True, "payload": param_whatsapp}
            elif len(variables) == whatsappVariableCount:
                dynamic_data = {}
                for i, var in enumerate(variables, 1):
                    dynamic_data[f"key{i}"] = var
                
                param_whatsapp["client_data"]["dynamic_data"] = dynamic_data
                return {"success": True, "payload": param_whatsapp}
            else:
                return {"success": False, "error": f"Variable Mismatch: Expected {whatsappVariableCount} or {whatsappVariableCount + 1} variables, got {len(variables)}"}
        
        # Case 2: dynamicCtaValidate != "NA" && whatsappVariableCount == "0"
        elif dynamicCtaValidate != "NA" and whatsappVariableCount == 0:
            param_whatsapp["client_data"]["dynamic_cta"] = dynamicCta
            return {"success": True, "payload": param_whatsapp}
        
        # Case 3: dynamicCtaValidate == "NA" && whatsappVariableCount == "0"  
        elif dynamicCtaValidate == "NA" and whatsappVariableCount == 0:
            if not variables:
                return {"success": False, "error": "No Link generated or Dynamic CTA Not available"}
            elif len(variables) == 1:
                param_whatsapp["client_data"]["dynamic_cta"] = variables[0]
                return {"success": True, "payload": param_whatsapp}
            else:
                return {"success": False, "error": "Variable Mismatch"}
        
        # Case 4: dynamicCtaValidate != "NA" && whatsappVariableCount != "0"
        elif dynamicCtaValidate != "NA" and whatsappVariableCount != 0:
            if len(variables) == whatsappVariableCount:
                dynamic_data = {}
                for i, var in enumerate(variables, 1):
                    dynamic_data[f"key{i}"] = var
                
                param_whatsapp["client_data"]["dynamic_data"] = dynamic_data
                param_whatsapp["client_data"]["dynamic_cta"] = dynamicCta
                return {"success": True, "payload": param_whatsapp}
            else:
                return {"success": False, "error": f"Variable Mismatch: Expected {whatsappVariableCount} variables, got {len(variables)}"}
        
        return {"success": False, "error": "Invalid configuration"}
        
    except Exception as e:
        print(f"Error building payload: {e}")
        return {"success": False, "error": str(e)}

# SMS payload 
def build_sms_payload(template, mobile_number, variables):
    """
        SMS payload 
    """
    try:
        sms_header = template.get('SMS_Header')
        sms_content = template.get('SMS_Template_Content')
        template_id = template.get('Template_ID')
        
        if not sms_content or not template_id:
            return {"success": False, "error": "No Template ID or Content Found in the SMS Template"}
        
        # Process variables if provided
        if variables:
            variable_count = len(variables)
            
            # Check if template expects this many variables
            if f"#VAR_{variable_count}" in sms_content.upper():
                for i, var in enumerate(variables, 1):
                    # Handle special case for phone number formatting
                    if str(var) == "2238237006":
                        var = "02238237006"
                    
                    sms_content = sms_content.replace(f"#VAR_{i}", str(var))
            else:
                return {"success": False, "error": "SMS Variable count Mismatch"}
        
        # Check if all variables are replaced
        if "#VAR_" in sms_content.upper():
            return {"success": False, "error": "In SMS Template variables are present, but no variables Passed"}
        
        payload = {
            "sender_id": sms_header,
            "to": f"+91{mobile_number}",
            "sms_type": "T",
            "sms_content_type": "Static",
            "dlt_entity_id": "1201167971793052243",
            "body": sms_content,
            "dlt_template_id": template_id,
            "application": "zoho"
        }
        
        return {"success": True, "payload": payload}
        
    except Exception as e:
        print(f"Error building SMS payload: {e}")
        return {"success": False, "error": str(e)}
    
# api call
def send_whatsapp_message(payload):

    try:
        # Step 1: Get auth token 
        auth_data = {
            "username": "notifications@jiofinance.com",
            "password": "Success@123",
            "bot_id": "1"
        }
        
        auth_url = f"{WHATSAPP_BASE}/get-auth-token/"
        print(f"DEBUG: Auth URL: {auth_url}")
        print(f"DEBUG: Auth data: {auth_data}")
        
        auth_response = requests.post(auth_url, json=auth_data, timeout=30)
        
        print(f"DEBUG: Auth response status: {auth_response.status_code}")
        print(f"DEBUG: Auth response: {auth_response.text}")
        
        if auth_response.status_code != 200:
            return {"success": False, "status": "failed", "error": f"Auth token failed: {auth_response.status_code} - {auth_response.text}"}
        
        auth_result = auth_response.json()
        auth_token = auth_result.get('auth_token')
        
        if not auth_token:
            return {"success": False, "status": "failed", "error": f"No auth token in response: {auth_result}"}
        
        payload["authorization"] = auth_token
        
        print(f"DEBUG: Final WhatsApp payload: {json.dumps(payload, indent=2)}")
        
        # Step 2: Send message
        send_url = f"{WHATSAPP_BASE}/send-event-based-triggered-whatsapp-campaign/"
        send_response = requests.post(send_url, json=payload, timeout=30)
        
        print(f"DEBUG: Send response status: {send_response.status_code}")
        print(f"DEBUG: Send response: {send_response.text}")
        
        if send_response.status_code == 200:
            result = send_response.json()
            status_code = result.get('status', 0)
            
            if status_code == 200:
                print("WhatsApp sent successfully!")
                return {"success": True, "status": "delivered", "response": result}
            else:
                print(f"WhatsApp failed with status: {status_code}")
                return {"success": False, "status": "not delivered", "response": result}
        else:
            return {"success": False, "status": "failed", "error": f"HTTP {send_response.status_code}: {send_response.text}"}
            
    except Exception as e:
        print(f"Error sending WhatsApp: {e}")
        return {"success": False, "status": "failed", "error": str(e)}
    
# api call for sms
def send_sms_message(payload):
    try:
        # Step 1: Get access token
        auth_credentials = os.environ.get('SMS_AUTH_CREDENTIALS', 'a1Vvc1JjR0lsRDBoNTJuUXJhTlpMaWZNS1dqWjd1aHI6ekdUZkhKZ0U2UEVJWkpPcw==')
        
        token_data = {"grant_type": "client_credentials"}
        token_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth_credentials}"
        }
        
        token_url = f"{SMS_BASE}/getToken"
        
        print(f"DEBUG: SMS Token URL: {token_url}")
        print(f"DEBUG: SMS Token data: {token_data}")
        print(f"DEBUG: SMS Token headers: {token_headers}")
        
        token_response = requests.post(token_url, data=token_data, headers=token_headers, timeout=10)
        
        print(f"DEBUG: SMS Token response status: {token_response.status_code}")
        print(f"DEBUG: SMS Token response: {token_response.text}")
        
        # Handle 403 Forbidden specifically
        if token_response.status_code == 403:
            return {
                "success": False, 
                "status": "Not sent", 
                "error": "SMS API Credentials Invalid (403 Forbidden) - Check with SMS provider"
            }
        
        if token_response.status_code != 200:
            return {
                "success": False, 
                "status": "Not sent", 
                "error": f"SMS Token API failed: {token_response.status_code} - {token_response.text[:100]}"
            }
        
        # Try to parse JSON response
        try:
            token_result = token_response.json()
        except json.JSONDecodeError:
            return {
                "success": False, 
                "status": "Not sent", 
                "error": f"SMS API returned non-JSON: {token_response.text[:100]}"
            }
        
        print(f"DEBUG: SMS Token result: {token_result}")
        
        if 'access_token' not in token_result:
            return {
                "success": False, 
                "status": "Not sent", 
                "error": f"No access token in response: {token_result}"
            }
        
        access_token = token_result['access_token']
        
        print(f"DEBUG: SMS Access token obtained: {access_token[:20]}...")
        print(f"DEBUG: SMS Payload: {json.dumps(payload, indent=2)}")
        
        # Step 2: Send SMS
        send_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        
        send_url = f"{SMS_BASE}/send"
        print(f"DEBUG: SMS Send URL: {send_url}")
        
        send_response = requests.post(send_url, json=payload, headers=send_headers, timeout=10)
        
        print(f"DEBUG: SMS Send response status: {send_response.status_code}")
        print(f"DEBUG: SMS Send response: {send_response.text}")
        
        if send_response.status_code == 200:
            result = send_response.json()
            status = result.get('status', '')
            
            if status == "success":
                print("SMS sent successfully!")
                return {"success": True, "status": "Sent", "response": result}
            else:
                print(f"SMS failed with status: {status}")
                return {"success": False, "status": "Not sent", "response": result}
        else:
            return {
                "success": False, 
                "status": "Not sent", 
                "error": f"SMS Send failed: {send_response.status_code} - {send_response.text[:100]}"
            }
            
    except requests.exceptions.Timeout:
        return {"success": False, "status": "Not sent", "error": "SMS API timeout"}
    except Exception as e:
        print(f"Error sending SMS: {e}")
        return {"success": False, "status": "Not sent", "error": f"Exception: {str(e)}"}

# updaterecord
def update_crm_record(record_id, result, crm_token):
    """
        zoho.crm.updateRecord("Communication_Channels",RecordID,{"Whatsapp_status":"Delivered"}); - python version
    """
    try:
        headers = {
            "Authorization": f"Zoho-oauthtoken {crm_token}",
            "Content-Type": "application/json"
        }
        
        # Prepare update data 
        update_data = {
            "Whatsapp_status": "Delivered" if result.get('status') == 'delivered' else "Not Delivered",
            "Whatsapp_Response": str(result.get('response', result.get('error', '')))[:255]  # Limit length
        }
        
        url = f"{ZOHO_CRM_BASE}/Communication_Channels/{record_id}"
        payload = {"data": [update_data]}
        
        print(f"DEBUG: CRM Update URL: {url}")
        print(f"DEBUG: CRM Update payload: {json.dumps(payload, indent=2)}")
        print(f"DEBUG: CRM Update headers: {headers}")
        
        response = requests.put(url, headers=headers, json=payload, timeout=30)
        
        print(f"DEBUG: CRM Update response status: {response.status_code}")
        print(f"DEBUG: CRM Update response: {response.text}")
        
        if response.status_code == 200:
            print(f"Updated CRM record: {record_id}")
        else:
            print(f"Failed to update CRM: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Error updating CRM: {e}")

# update sms record
def update_sms_crm_record(record_id, result, crm_token):
    """
        SMS CRM update
    """
    try:
        headers = {
            "Authorization": f"Zoho-oauthtoken {crm_token}",
            "Content-Type": "application/json"
        }
        
        # Prepare update data 
        update_data = {
            "SMS_Status": result.get('status', 'Not sent'),
            "SMS_Response": str(result.get('response', result.get('error', '')))[:255]  # Limit length
        }
        
        url = f"{ZOHO_CRM_BASE}/Communication_Channels/{record_id}"
        payload = {"data": [update_data]}
        
        print(f"DEBUG: SMS CRM Update URL: {url}")
        print(f"DEBUG: SMS CRM Update payload: {json.dumps(payload, indent=2)}")
        
        response = requests.put(url, headers=headers, json=payload, timeout=30)
        
        print(f"DEBUG: SMS CRM Update response status: {response.status_code}")
        print(f"DEBUG: SMS CRM Update response: {response.text}")
        
        if response.status_code == 200:
            print(f"Updated SMS CRM record: {record_id}")
        else:
            print(f"Failed to update SMS CRM: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Error updating SMS CRM: {e}")

def create_response(status_code, data):
    """Create API Gateway response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(data)
    }