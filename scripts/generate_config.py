#!/usr/bin/env python3
"""
Generate configuration files from templates with environment variable substitution
Works in both Docker (Balena) and standalone deployment
"""

import os
import sys
from pathlib import Path


def load_env_file(env_path):
    """Load environment variables from .env file"""
    if not env_path.exists():
        return {}

    env_vars = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    return env_vars


def generate_config():
    """Generate config files from templates"""

    # Detect if running in Docker or standalone
    script_dir = Path(__file__).parent.parent  # Project root

    if Path('/app/config').exists():
        # Docker/Balena environment
        config_dir = Path('/app/config')
        output_dir = Path('/data/config')
    else:
        # Standalone environment
        config_dir = script_dir / 'config'
        output_dir = Path('/data/config')

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load from .env file if it exists (standalone mode)
    env_file = script_dir / '.env'
    file_env_vars = load_env_file(env_file) if env_file.exists() else {}

    # Environment variables (prefer .env file, fallback to system env)
    env_vars = {
        'SITE_ID': file_env_vars.get('SITE_ID') or os.getenv('SITE_ID', 'SITE_UNKNOWN'),
        'SITE_NAME': file_env_vars.get('SITE_NAME') or os.getenv('SITE_NAME', 'Unknown Site'),
        'SITE_LOCATION': file_env_vars.get('SITE_LOCATION') or os.getenv('SITE_LOCATION', 'Unknown'),
        'SITE_CONTACT': file_env_vars.get('SITE_CONTACT') or os.getenv('SITE_CONTACT', ''),
        'TRANSFORMER_RATING': file_env_vars.get('TRANSFORMER_RATING') or os.getenv('TRANSFORMER_RATING', ''),
        'TRANSFORMER_TYPE': file_env_vars.get('TRANSFORMER_TYPE') or os.getenv('TRANSFORMER_TYPE', 'Distribution'),
        'IOT_ENDPOINT': file_env_vars.get('IOT_ENDPOINT') or os.getenv('IOT_ENDPOINT', ''),
        'IOT_THING_NAME': file_env_vars.get('IOT_THING_NAME') or os.getenv('IOT_THING_NAME', ''),
        'AWS_REGION': file_env_vars.get('AWS_REGION') or os.getenv('AWS_REGION', 'us-east-1'),
        'AWS_IOT_ENABLED': file_env_vars.get('AWS_IOT_ENABLED') or os.getenv('AWS_IOT_ENABLED', 'false'),
        'FTP_HOST': file_env_vars.get('FTP_HOST') or os.getenv('FTP_HOST', ''),
        'FTP_USERNAME': file_env_vars.get('FTP_USERNAME') or os.getenv('FTP_USERNAME', ''),
        'FTP_PASSWORD': file_env_vars.get('FTP_PASSWORD') or os.getenv('FTP_PASSWORD', ''),
        'FTP_ENABLED': file_env_vars.get('FTP_ENABLED') or os.getenv('FTP_ENABLED', 'false'),
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