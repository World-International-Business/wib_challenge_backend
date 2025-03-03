import os
from pathlib import Path

import dotenv

dotenv_path = Path(__file__).resolve().parent.parent.parent / '.env'

dotenv.load_dotenv(dotenv_path=dotenv_path)

if os.getenv('DEBUG', 'True') == 'True':
    from .development import *
else:
    from .production import *
