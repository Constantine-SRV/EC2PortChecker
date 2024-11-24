# Variables
$FUNCTION_NAME = "EC2IPAccessChecker"
$ROLE_NAME = "LambdaEC2AccessRole"
$POLICY_ARN = "arn:aws:iam::637423446150:policy/LambdaEC2ReadOnly"
$REGION = "eu-north-1"

# Function to delete all non-default policy versions
function Delete-NonDefaultPolicyVersions {
    param (
        [string]$PolicyArn
    )
    
    # List all policy versions
    $versions = aws iam list-policy-versions --policy-arn $PolicyArn | ConvertFrom-Json
    
    foreach ($version in $versions.Versions) {
        if (-not $version.IsDefaultVersion) {
            Write-Output "Deleting policy version: $($version.VersionId)"
            aws iam delete-policy-version --policy-arn $PolicyArn --version-id $version.VersionId
        }
    }
}

# Step 1: Delete Lambda Function (if exists)
$lambda_exists = aws lambda get-function --function-name $FUNCTION_NAME --region $REGION 2>$null
if ($lambda_exists) {
    Write-Output "Deleting Lambda function: $FUNCTION_NAME"
    aws lambda delete-function --function-name $FUNCTION_NAME --region $REGION
} else {
    Write-Output "Lambda function $FUNCTION_NAME does not exist. Skipping deletion."
}

# Step 2: Detach Policy from IAM Role (if role exists)
$role_exists = aws iam get-role --role-name $ROLE_NAME 2>$null
if ($role_exists) {
    Write-Output "Detaching policy $POLICY_ARN from role $ROLE_NAME"
    aws iam detach-role-policy --role-name $ROLE_NAME --policy-arn $POLICY_ARN
} else {
    Write-Output "IAM role $ROLE_NAME does not exist. Skipping policy detachment."
}

# Step 3: Delete All Non-Default Policy Versions (if policy exists)
$policy_exists = aws iam get-policy --policy-arn $POLICY_ARN 2>$null
if ($policy_exists) {
    Write-Output "Deleting non-default versions of policy: $POLICY_ARN"
    Delete-NonDefaultPolicyVersions -PolicyArn $POLICY_ARN
    
    # Step 4: Delete IAM Policy
    Write-Output "Deleting IAM policy: $POLICY_ARN"
    aws iam delete-policy --policy-arn $POLICY_ARN
} else {
    Write-Output "IAM policy $POLICY_ARN does not exist. Skipping policy deletion."
}

# Step 5: Delete IAM Role (if exists)
if ($role_exists) {
    Write-Output "Deleting IAM role: $ROLE_NAME"
    aws iam delete-role --role-name $ROLE_NAME
} else {
    Write-Output "IAM role $ROLE_NAME does not exist. Skipping role deletion."
}

Write-Output "Cleanup completed successfully."
