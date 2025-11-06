#!/usr/bin/env python3
"""
Generate configuration files from templates with environment variable substitution
"""

import os
import sys
from pathlib import Path


def generate_config():
    """Generate config files from templates"""
    
    config_dir = Path('/app/config')
    output_dir = Path('/data/config')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Environment variables
    env_vars = {
        'SITE_ID': os.getenv('SITE_ID', 'SITE_UNKNOWN'),
        'SITE_NAME': os.getenv('SITE_NAME', 'Unknown Site'),
        'SITE_ADDRESS': os.getenv('SITE_ADDRESS', 'Unknown'),
        'TRANSFORMER_SN': os.getenv('TRANSFORMER_SN', 'UNKNOWN'),
        'IOT_ENDPOINT': os.getenv('IOT_ENDPOINT', ''),
        'IOT_THING_NAME': os.getenv('IOT_THING_NAME', ''),
        'AWS_REGION': os.getenv('AWS_REGION', 'us-east-1'),
        'S3_BUCKET_NAME': os.getenv('S3_BUCKET_NAME', ''),
        'FTP_HOST': os.getenv('FTP_HOST', ''),
        'FTP_USERNAME': os.getenv('FTP_USERNAME', ''),
        'FTP_PASSWORD': os.getenv('FTP_PASSWORD', ''),
    }
    
    # Process each template
    templates = [
        'site_config.template.yaml',
        'aws_config.template.yaml'
    ]
    
    for template_name in templates:
        template_path = config_dir / template_name
        output_name = template_name.replace('.template', '')
        output_path = output_dir / output_name
        
        # Skip if output already exists
        if output_path.exists():
            print(f"Config already exists: {output_path}")
            continue
        
        if not template_path.exists():
            print(f"Template not found: {template_path}")
            continue
        
        # Read template
        with open(template_path) as f:
            content = f.read()
        
        # Substitute variables
        for key, value in env_vars.items():
            content = content.replace(f'{{{{{key}}}}}', str(value))
        
        # Write output
        with open(output_path, 'w') as f:
            f.write(content)
        
        print(f"Generated: {output_path}")
    
    print("Configuration generation complete")


if __name__ == '__main__':
    try:
        generate_config()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)