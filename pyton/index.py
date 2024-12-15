import json
import boto3
import socket
import csv
import io
import logging
from botocore.exceptions import NoCredentialsError, ClientError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Email configuration
SENDER_EMAIL = '5625@pam4.com'
RECIPIENT_EMAIL = '5625@pam4.com'
SES_REGION = 'us-east-1'  # SES region
SES_CLIENT = boto3.client('ses', region_name=SES_REGION)

# Configuration variables to control email content
is_result_table_in_email_body = False  # Set to True to include the table in the email body
is_result_table_as_attached = True      # Set to True to include the table as a CSV attachment

def lambda_handler(event, context):
    try:
        # Initialize STS client to get Account ID
        sts_client = boto3.client('sts')
        account_id = sts_client.get_caller_identity().get('Account')
        account_suffix = account_id[-4:]  # Extract the last 4 digits of the Account ID

        logger.info(f"Account ID: {account_id}, Suffix: {account_suffix}")

        # Retrieve all available AWS regions
        regions = get_all_regions()
        results = []
        total_instances = 0
        open_port_instances = 0

        # Iterate through each region to gather EC2 instance information
        for region in regions:
            logger.info(f"Processing region: {region}")
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
        summary = (
            f"Number of Instances validated: {total_instances} <br> "
            f"Number of instances with Status of Port 22 Open: {open_port_instances} <br><br>"
        )
        
        # Log the summary
        logger.info(summary)

        # Format the results into an HTML table with the summary and account suffix
        html_body = format_results_as_html(results, summary, account_suffix) if is_result_table_in_email_body else generate_summary_html(summary, account_suffix)

        # Generate CSV content if attachment is required
        csv_content = generate_csv(results) if is_result_table_as_attached else None

        # Create the email subject with the last 4 digits of the Account ID
        email_subject = f'Daily EC2 Port 22 Status Report - Account {account_suffix}'

        # Send the email via SES with optional CSV attachment
        send_email_with_attachment(
            sender=SENDER_EMAIL,
            recipient=RECIPIENT_EMAIL,
            subject=email_subject,
            body_html=html_body,
            attachment_filename='EC2_Port22_Status_Report.csv' if is_result_table_as_attached else None,
            attachment_content=csv_content
        )
        
        # Log successful email sending
        logger.info("Email sent successfully.")
        
        return {
            'statusCode': 200,
            'body': json.dumps('Email with attachment sent successfully!')
        }

    except NoCredentialsError:
        logger.error('Error: AWS credentials not found. Please configure them.')
        return {
            'statusCode': 500,
            'body': json.dumps('Error: AWS credentials not found. Please configure them.')
        }
    except ClientError as e:
        logger.error(f'AWS ClientError: {e}')
        return {
            'statusCode': 500,
            'body': json.dumps(f'AWS ClientError: {e}')
        }
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        return {
            'statusCode': 500,
            'body': json.dumps(f'Unexpected error: {e}')
        }

def get_all_regions():
    """
    Retrieves a list of all available AWS regions.
    """
    ec2_client = boto3.client('ec2', region_name=SES_REGION)  # Initialize EC2 client using SES region
    try:
        regions_response = ec2_client.describe_regions(AllRegions=True)
        regions = [
            region['RegionName'] 
            for region in regions_response['Regions'] 
            if region['OptInStatus'] in ['opt-in-not-required', 'opted-in']
        ]
        logger.info(f"Retrieved regions: {regions}")
        return regions
    except ClientError as e:
        logger.error(f"Error retrieving regions: {e}")
        raise e

def get_ec2_instances(region):
    """
    Retrieves a list of running EC2 instances in the specified region.
    """
    ec2 = boto3.resource('ec2', region_name=region)
    instances = ec2.instances.filter(
        Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]
    )
    return instances

def get_instance_name(instance):
    """
    Retrieves the name of the instance from its tags.
    """
    name = 'N/A'
    if instance.tags:
        for tag in instance.tags:
            if tag['Key'] == 'Name':
                name = tag['Value']
                break
    return name

def get_instance_owner(instance):
    """
    Retrieves the OWNER tag of the instance or returns a dash if not present.
    """
    owner = '-'
    if instance.tags:
        for tag in instance.tags:
            if tag['Key'] == 'OWNER':
                owner = tag['Value']
                break
    return owner

def is_port_open(ip, port=22, timeout=3):
    """
    Checks if the specified port is open on the given IP.
    """
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (socket.timeout, socket.error):
        return False

def generate_csv(results):
    """
    Generates CSV content from the results.
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['Region', 'Name', 'Owner', 'Public IP', 'Port 22 Open', 'Instance ID'])
    writer.writeheader()
    for row in results:
        writer.writerow(row)
    csv_data = output.getvalue()
    logger.info("CSV content generated successfully.")
    return csv_data

def send_email_with_attachment(sender, recipient, subject, body_html, attachment_filename=None, attachment_content=None):
    """
    Sends an email via SES with an optional attachment.
    """
    # Create a multipart/mixed parent container.
    msg = MIMEMultipart('mixed')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient

    # Create a multipart/alternative child container for the email body.
    msg_body = MIMEMultipart('alternative')

    # Attach the HTML part to the child container.
    html_part = MIMEText(body_html, 'html')
    msg_body.attach(html_part)

    # Attach the multipart/alternative child container to the multipart/mixed parent container.
    msg.attach(msg_body)

    # If attachment is required, encode and attach it.
    if attachment_content and attachment_filename:
        attachment_part = MIMEApplication(attachment_content, _subtype='csv')
        attachment_part.add_header('Content-Disposition', 'attachment', filename=attachment_filename)
        msg.attach(attachment_part)
        logger.info(f"Attached CSV file: {attachment_filename}")

    # Send the email via SES
    try:
        response = SES_CLIENT.send_raw_email(
            Source=sender,
            Destinations=[recipient],
            RawMessage={
                'Data': msg.as_string(),
            }
        )
        logger.info(f"Email sent! Message ID: {response['MessageId']}")
    except ClientError as e:
        logger.error(f"Error sending email: {e.response['Error']['Message']}")
        raise e

def format_results_as_html(results, summary, account_suffix):
    """
    Formats the results into an HTML table with a summary and account suffix.
    """
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
    <h3>Daily EC2 Port 22 Status Report - Account {account_suffix}</h3>
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
        row_class = 'open-port' if item['Port 22 Open'] == 'Open' else 'closed-port'
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
    logger.info("HTML body formatted successfully.")
    return html

def generate_summary_html(summary, account_suffix):
    """
    Generates a simple HTML body with only the summary and account suffix.
    """
    html = f"""<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
        }}
    </style>
</head>
<body>
    <h3>Daily EC2 Port 22 Status Report - Account {account_suffix}</h3>
    {summary}
</body>
</html>
"""
    logger.info("Summary HTML formatted successfully.")
    return html
