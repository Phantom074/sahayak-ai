
terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.30" }
  }
  backend "s3" {
    bucket  = "sahayak-terraform-state"
    key     = "sahayak/dev/terraform.tfstate"
    region  = "ap-south-1"
    encrypt = true
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = { Project = "SahayakAI", Environment = "dev", ManagedBy = "Terraform" }
  }
}

module "networking"   { source = "../../modules/networking";   environment = var.environment; vpc_cidr = "10.0.0.0/16" }
module "security"     { source = "../../modules/security";     environment = var.environment }
module "storage"      { source = "../../modules/storage";      environment = var.environment; kms_key_arn = module.security.kms_key_arn; private_subnet_ids = module.networking.private_subnet_ids }
module "compute"      { source = "../../modules/compute";      environment = var.environment; private_subnet_ids = module.networking.private_subnet_ids; lambda_sg_id = module.networking.lambda_sg_id; opensearch_endpoint = module.storage.opensearch_endpoint; sessions_table_name = module.storage.sessions_table_name; users_table_name = module.storage.users_table_name; schemes_table_name = module.storage.schemes_table_name; audio_input_bucket = module.storage.audio_input_bucket; audio_output_bucket = module.storage.audio_output_bucket; kms_key_arn = module.security.kms_key_arn }
module "messaging"    { source = "../../modules/messaging";    environment = var.environment }
module "observability"{ source = "../../modules/observability"; environment = var.environment; lambda_function_names = module.compute.lambda_function_names }
