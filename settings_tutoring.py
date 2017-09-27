import os

from collections import defaultdict
from settings_base import _settings_base

settings = {
    'username': 'dsporteous',
    'password': os.environ['UNIMELBPASSTUTOR'],
    'date_range': '9-12',
}

# Merge settings_base and settings.
# If there is a clash in keys, we use the value in settings.
settings = defaultdict(lambda: None, {**_settings_base, **settings})
