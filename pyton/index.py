import json
import boto3
import socket
from botocore.exceptions import NoCredentialsError, ClientError

sender_email = '5625@pam4.com'
recipient_email = '5625@pam4.com'
SES_REGION = 'us-east-1'  # SES region
ses_client = boto3.client('ses', region_name=SES_REGION)

def lambda_handler(event, context):
    try:
        # Get the Account ID and extract the last 4 digits
        sts_client = boto3.client('sts')
        account_id = sts_client.get_caller_identity().get('Account')
        account_suffix = account_id[-4:]

        # Retrieve the list of all AWS regions
        regions = get_all_regions()
        results = []
        total_instances = 0
        open_port_instances = 0

        for region in regions:
            print(f"Processing region: {region}")
            instances = get_ec2_instances(region)
            
            for instance in instances:
                total_instances += 1
                instance_id = instance.id
                name = get_instance_name(instance)
                owner = get_instance_owner(instance)
                public_ip = instance.public_ip_address if instance.public_ip_address else 'N/A'
                port_open = 'Closed'
                
                if public_ip != 'N/A':
                    if is_port_open(public_ip):
                        port_open = 'Open'
                        open_port_instances += 1
                
                results.append({
                    'Region': region,
                    'Name': name,
                    'Owner': owner,
                    'Public IP': public_ip,
                    'Port 22 Open': port_open,
                    'Instance ID': instance_id
                })
        
        # Create the summary string
        summary = f"Number of Instances validated: {total_instances} <br> Number of instances with Status of Port 22 Open: {open_port_instances} <br><br>"

        # Format the results into an HTML table with the summary
        html_body = format_results_as_html(results, summary)
        
        # Create the email subject with the last 4 digits of the Account ID
        email_subject = f'Daily EC2 Port 22 Status Report - Account {account_suffix}'
        
        # Send the email via SES
        send_email(
            sender=sender_email,               
            recipient=recipient_email,            
            subject=email_subject,
            body_html=html_body
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps('Email sent successfully!')
        }

    except NoCredentialsError:
        return {
            'statusCode': 500,
            'body': json.dumps('Error: AWS credentials not found. Please configure them.')
        }
    except ClientError as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f'AWS ClientError: {e}')
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f'Unexpected error: {e}')
        }

def get_all_regions():
    """Retrieves a list of all available AWS regions."""
    ec2_client = boto3.client('ec2', region_name=SES_REGION)  # Initialize EC2 client using SES region
    try:
        regions_response = ec2_client.describe_regions(AllRegions=True)
        regions = [
            region['RegionName'] 
            for region in regions_response['Regions'] 
            if region['OptInStatus'] in ['opt-in-not-required', 'opted-in']
        ]
        return regions
    except ClientError as e:
        print(f"Error retrieving regions: {e}")
        raise e

def get_ec2_instances(region):
    """Retrieves a list of running EC2 instances in the specified region."""
    ec2 = boto3.resource('ec2', region_name=region)
    instances = ec2.instances.filter(
        Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
    )
    return instances

def get_instance_name(instance):
    """Retrieves the name of the instance from its tags."""
    name = 'N/A'
    if instance.tags:
        for tag in instance.tags:
            if tag['Key'] == 'Name':
                name = tag['Value']
                break
    return name

def get_instance_owner(instance):
    """Retrieves the OWNER tag of the instance or returns a dash if not present."""
    owner = '-'
    if instance.tags:
        for tag in instance.tags:
            if tag['Key'] == 'OWNER':
                owner = tag['Value']
                break
    return owner

def is_port_open(ip, port=22, timeout=3):
    """Checks if the specified port is open on the given IP."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (socket.timeout, socket.error):
        return False

def send_email(sender, recipient, subject, body_html):
    """Sends an email via SES."""
    try:
        response = ses_client.send_email(
            Source=sender,
            Destination={
                'ToAddresses': [
                    recipient,
                ],
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Html': {
                        'Data': body_html,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
    except ClientError as e:
        print(f"Error sending email: {e.response['Error']['Message']}")
        raise e
    else:
        print(f"Email sent! Message ID: {response['MessageId']}")

def format_results_as_html(results, summary):
    """Formats the results into an HTML table with a summary."""
    # Start the HTML structure with styles
    html = f"""<html>
<head>
    <style>
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            border: 1px solid #dddddd;
            text-align: left;
            padding: 8px;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        .open-port {{
            background-color: #d4edda; /* Light green background */
            color: #155724; /* Dark green text */
        }}
        .closed-port {{
            background-color: #f8d7da; /* Light red background */
            color: #721c24; /* Dark red text */
        }}
    </style>
</head>
<body>
    <h2>Daily EC2 Port 22 Status Report</h2>
    {summary}
    <table>
        <tr>
            <th>Region</th>
            <th>Name</th>
            <th>Owner</th>
            <th>Public IP</th>
            <th>Port 22 Status</th>
            <th>Instance ID</th>
        </tr>
"""

    # Add table rows with conditional styling
    for item in results:
        if item['Port 22 Open'] == 'Open':
            row_class = 'open-port'
        else:
            row_class = 'closed-port'
        
        html += f"""
        <tr class="{row_class}">
            <td>{item['Region']}</td>
            <td>{item['Name']}</td>
            <td>{item['Owner']}</td>
            <td>{item['Public IP']}</td>
            <td>{item['Port 22 Open']}</td>
            <td>{item['Instance ID']}</td>
        </tr>
"""

    # Close the HTML structure
    html += """
    </table>
</body>
</html>
"""
    return html
