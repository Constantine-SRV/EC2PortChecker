import json
import boto3
import socket
from botocore.exceptions import NoCredentialsError, ClientError

sender_email='5625@pam4.com'
recipient_email='5625@pam4.com'
SES_REGION = 'us-east-1' # SES region
ses_client = boto3.client('ses', region_name=SES_REGION)

def lambda_handler(event, context):
    try:
        # Retrieve the list of all AWS regions
        regions = get_all_regions()
        results = []
        
        for region in regions:
            print(f"Processing region: {region}")
            instances = get_ec2_instances(region)
            
            for instance in instances:
                instance_id = instance.id
                name = get_instance_name(instance)
                public_ip = instance.public_ip_address if instance.public_ip_address else 'N/A'
                port_open = 'No'
                
                if public_ip != 'N/A':
                    if is_port_open(public_ip):
                        port_open = 'Yes'
                
                results.append({
                    'Region': region,
                    'Instance ID': instance_id,
                    'Name': name,
                    'Public IP': public_ip,
                    'Port 22 Open': port_open
                })
        
        # Format the results into an HTML table
        html_body = format_results_as_html(results)
        
        # Send the email via SES
        send_email(
            sender=sender_email,               
            recipient=recipient_email,            
            subject='Daily EC2 Port 22 Status Report',
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

def format_results_as_html(results):
    """Formats the results into an HTML table."""
    # Start the HTML structure with styles
    html = """<html>
<head>
    <style>
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            border: 1px solid #dddddd;
            text-align: left;
            padding: 8px;
        }
        th {
            background-color: #f2f2f2;
        }
        .open-port {
            background-color: #f8d7da; /* Light red background */
            color: #721c24; /* Dark red text */
        }
    </style>
</head>
<body>
    <h2>Daily EC2 Port 22 Status Report</h2>
    <table>
        <tr>
            <th>Region</th>
            <th>Instance ID</th>
            <th>Name</th>
            <th>Public IP</th>
            <th>Port 22 Open</th>
        </tr>
"""
    # Add table rows with conditional styling
    for item in results:
        if item['Port 22 Open'] == 'Yes':
            row_class = 'open-port'
        else:
            row_class = ''
        
        html += f"""
        <tr class="{row_class}">
            <td>{item['Region']}</td>
            <td>{item['Instance ID']}</td>
            <td>{item['Name']}</td>
            <td>{item['Public IP']}</td>
            <td>{item['Port 22 Open']}</td>
        </tr>
"""
    # Close the HTML structure
    html += """
    </table>
</body>
</html>
"""
    return html
