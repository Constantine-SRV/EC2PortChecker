# EC2PortChecker

The EC2PortChecker project demonstrates:

1. **Configuring Policies for Read-Only Access**: AWS Lambda functions with read-only access to EC2 configurations.
2. **Configuring Policies to Allow Email Sending**: AWS Lambda functions with permissions to send emails.
3. **Using AWS SES for Email Delivery**: Integration with AWS Simple Email Service (SES) for sending emails.
4. **Adding and Verifying Email Addresses**: Setting up and confirming the email addresses used for sending emails.

### Required Policies

- **Trust Policy**: [trust-policy.json](https://github.com/Constantine-SRV/EC2PortChecker/blob/main/terraform/trust-policy.json)
- **EC2 and SES Policy**: [ec2-ses-policy.json](https://github.com/Constantine-SRV/EC2PortChecker/blob/main/terraform/ec2-ses-policy.json)

### Terraform Configuration

- **Policy and Lambda Function Setup**: [lambda.tf](https://github.com/Constantine-SRV/EC2PortChecker/blob/main/terraform/lambda.tf)

### Lambda Function Code

- **Function Script**: [index.py](https://github.com/Constantine-SRV/EC2PortChecker/blob/main/pyton/index.py)

In lines 6-7 of the `index.py` file, specify the sender and recipient email addresses and the SES region where the email is configured. This must match the region specified in the second line of the `lambda.tf` file.

### AWS CLI Commands for Email Verification

1. **Verify Email Identity**:
    ```bash
    aws ses verify-email-identity --email-address 5625@pam4.com --region us-east-1
    ```
    An email will be sent to the specified address with a link that must be opened to complete verification.

2. **Check Verification Status**:
    ```bash
    aws ses get-identity-verification-attributes --identities 5625@pam4.com --region us-east-1
    ```

3. **List Verified Email Addresses**:
    ```bash
    aws ses list-identities --identity-type EmailAddress --region us-east-1
    ```
