# config.py
class Config:
    # Tally Configuration
    TALLY_URL = "http://localhost:9000"  # Change if Tally runs on different machine
    TALLY_COMPANY = "Your Company Name"  # Exact name as in Tally
    TALLY_PORT = 9000
    
    # Sync Settings
    AUTO_SYNC_NEW_ITEMS = True
    AUTO_SYNC_NEW_PARTIES = True
    BATCH_SIZE = 50  # Number of records per sync batch
    
    # Paths
    BACKUP_DIR = "backups"
    LOG_DIR = "logs"
    
    # Currency (Indian Settings)
    CURRENCY = "₹"
    GST_PERCENT = 18  # Default GST rate
    
# Update tally_integration.py to use config:
from config import Config

tally = TallyIntegration(
    tally_url=Config.TALLY_URL,
    company=Config.TALLY_COMPANY
)