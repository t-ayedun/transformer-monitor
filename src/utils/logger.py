"""
Logging Utility
Configures centralized logging
"""

import logging
import logging.config
import yaml
from pathlib import Path


def setup_logging():
    """Setup logging configuration"""
    config_path = Path('/app/config/logging_config.yaml')
    
    # Ensure log directory exists
    Path('/home/smartie/transformer_monitor_data/logs').mkdir(parents=True, exist_ok=True)
    
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
            logging.config.dictConfig(config)
    else:
        # Fallback to basic config
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('/home/smartie/transformer_monitor_data/logs/monitor.log')
            ]
        )
    
    logger = logging.getLogger(__name__)
    logger.info("Logging configured")