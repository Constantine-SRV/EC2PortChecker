provider "aws" {
  region = "us-east-1" # Replace with your desired AWS region
}

# Retrieve AWS Account ID
data "aws_caller_identity" "current" {}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "LambdaEC2AccessRole"

  assume_role_policy = file("${path.module}/trust-policy.json")

  description = "Role for EC2IPAccessChecker Lambda function with read-only access to EC2 and SES"
}

# IAM Policy for Lambda
resource "aws_iam_policy" "lambda_policy" {
  name        = "LambdaEC2ReadOnly"
  description = "Policy with read-only access to EC2 and SendEmail permissions for Lambda function"

  policy = file("${path.module}/ec2-ses-policy.json")
}

# Attach the IAM policy to the role
resource "aws_iam_role_policy_attachment" "lambda_policy_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

# Archive the Lambda function code from index.py
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../pyton/index.py" # Ensure the Lambda code is located in pyton/index.py
  output_path = "${path.module}/function.zip"
}

# Lambda Function
resource "aws_lambda_function" "ec2_ip_access_checker" {
  function_name = "EC2IPAccessChecker"
  role          = aws_iam_role.lambda_role.arn
  handler       = "index.lambda_handler"
  runtime       = "python3.9"
  timeout       = 30
  memory_size   = 128
  description    = "Lambda function to retrieve IP addresses of all EC2 instances across all regions in the account and send SES email report"

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  depends_on = [aws_iam_role_policy_attachment.lambda_policy_attach]
}

# Setup EventBridge for daily Lambda function trigger
resource "aws_cloudwatch_event_rule" "daily_lambda_trigger" {
  name                = "DailyEC2IPAccessCheckerTrigger"
  description         = "Trigger EC2IPAccessChecker Lambda function daily at 20:00 UTC (22:00 Cyprus time)"
  schedule_expression = "cron(0 20 * * ? *)" # Daily at 20:00 UTC (22:00 Cyprus time)
}

# Grant EventBridge permission to invoke the Lambda function
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ec2_ip_access_checker.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_lambda_trigger.arn
}

# Define the EventBridge target for the Lambda function
resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.daily_lambda_trigger.name
  target_id = "EC2IPAccessCheckerLambda"
  arn       = aws_lambda_function.ec2_ip_access_checker.arn
}
