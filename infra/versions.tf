terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Local backend by default (terraform.tfstate in this directory).
  # The state holds sensitive values (DB password, origin-verify header value),
  # so it must never be committed. README "State backend" explains moving it to S3.
  #
  # backend "s3" {
  #   bucket       = "dowonpact-tfstate-<계정 ID>"
  #   key          = "infra/terraform.tfstate"
  #   region       = "ap-northeast-2"
  #   profile      = "itbm"
  #   encrypt      = true
  #   use_lockfile = true
  # }
}
