# AWS Lambda Setup Script for EC2 IP Access Checker with SES Integration

# Variables
$email = "5625@pam4.com"               # SES email address to verify and use for sending reports
$region = "us-east-1"                   # AWS region for SES and Lambda
$functionName = "EC2IPAccessChecker"    # Lambda function name
$roleName = "LambdaEC2AccessRole"       # IAM role name
$policyName = "LambdaEC2ReadOnly"       # IAM policy name

# Retrieve AWS Account ID
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
Write-Output "Account ID: $ACCOUNT_ID"

# Function to check email verification status by searching for "Success" in the output
function Is-EmailVerified {
    param (
        [string]$Email,
        [string]$Region
    )
    
    $verificationOutput = aws ses get-identity-verification-attributes `
        --identities $Email `
        --region $Region

    # Check if the output contains "Success"
    if ($verificationOutput -like "*Success*") {
        return $true
    } else {
        return $false
    }
}

# Check SES Email Verification Status
$verificationStatus = Is-EmailVerified -Email $email -Region $region

if (-not $verificationStatus) {
    Write-Output "Email address $email is not verified. Sending verification email..."
    aws ses verify-email-identity `
        --email-address $email `
        --region $region

    Write-Output "A verification email has been sent to $email. Please verify the email."
    
    # Prompt the user to press Enter after verifying the email
    Read-Host "After verifying the email, press Enter to continue..."
    
    # Optionally, implement a loop to wait until the email is verified
    # Uncomment the following block to enable automatic checking

    # do {
    #     Write-Output "Checking email verification status..."
    #     $verificationStatus = Is-EmailVerified -Email $email -Region $region
    #     if (-not $verificationStatus) {
    #         Write-Output "Email not yet verified. Waiting for 30 seconds before rechecking..."
    #         Start-Sleep -Seconds 30
    #     }
    # } while (-not $verificationStatus)
    # Write-Output "Email address $email has been verified."
} else {
    Write-Output "Email address $email is already verified."
}

# Create IAM Role for Lambda
Write-Output "Creating IAM role: $roleName"
$role_creation = aws iam create-role `
    --role-name $roleName `
    --assume-role-policy-document file://trust-policy.json `
    --description "Role for EC2IPAccessChecker Lambda function with read-only access to EC2 and SES" `
    --output json

if ($role_creation -match "Role") {
    Write-Output "IAM role $roleName created successfully."
} else {
    Write-Output "Failed to create IAM role $roleName."
    exit 1
}

# Wait for a few seconds to ensure the role is fully propagated
Start-Sleep -Seconds 10

# Create Custom IAM Policy LambdaEC2ReadOnly
Write-Output "Creating IAM policy: $policyName"
$POLICY_OUTPUT = aws iam create-policy `
    --policy-name $policyName `
    --policy-document file://ec2-ses-policy.json `
    --description "Read-only access to EC2 and SendEmail permissions for Lambda function" `
    --output json

# Extract Policy ARN
$POLICY_ARN = ($POLICY_OUTPUT | ConvertFrom-Json).Policy.Arn
Write-Output "Policy ARN: $POLICY_ARN"

# Attach Policy to IAM Role
Write-Output "Attaching policy $POLICY_ARN to role $roleName"
aws iam attach-role-policy `
    --role-name $roleName `
    --policy-arn $POLICY_ARN

# Wait for a few seconds to ensure the policy is attached
Start-Sleep -Seconds 10

# Package Lambda Function Code into ZIP Archive
Write-Output "Packaging Lambda function code into function.zip"
Compress-Archive -Path index.py -DestinationPath function.zip -Force

# Create or Update Lambda Function
Write-Output "Checking if Lambda function exists: $functionName"
aws lambda get-function --function-name $functionName --region $region >$null 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Output "Lambda function exists. Updating function code."
    aws lambda update-function-code `
        --function-name $functionName `
        --zip-file fileb://function.zip `
        --region $region
} else {
    Write-Output "Lambda function does not exist. Creating new function."
    
    # Construct the IAM Role ARN correctly using double quotes for variable interpolation
    #arn:aws:iam::637423446150:role/LambdaEC2AccessRole 
    $ROLE_ARN = "arn:aws:iam::" + $ACCOUNT_ID+":role/" +$roleName
    Write-Output "Using IAM Role ARN: $ROLE_ARN"

    aws lambda create-function `
        --function-name $functionName `
        --runtime python3.9 `
        --role $ROLE_ARN `
        --handler index.lambda_handler `
        --zip-file fileb://function.zip `
        --timeout 30 `
        --memory-size 128 `
        --description "Lambda function to retrieve IP addresses of all EC2 instances across all regions in the account and send SES email report" `
        --region $region
}

# Invoke Lambda Function and Save Response
Write-Output "Invoking Lambda function: $functionName"
$invoke_response = aws lambda invoke `
    --function-name $functionName `
    --payload "{}" `
    response.json `
    --region $region

# Check if invocation was successful by searching for "StatusCode": 200 in the response


Get-Content response.json | ConvertFrom-Json | Select-Object -ExpandProperty body | ConvertFrom-Json | Format-List
# Optional: Clean up the function.zip file
#Remove-Item -Path function.zip -Force
