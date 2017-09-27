import os

from collections import defaultdict
from settings_base import _settings_base

settings = {
    'username': 'dstern',
    'password': os.environ['UNIMELBPASS'],
    'date_range': '1-12',
    'lecture_subfolder_name': 'Recordings',
    'uni_location': 'Dropbox/University/2017S2',
    # 'subject_folders': '',
    'subject_folders': {
        'SWEN30006': 'SWEN30006 - SMD',
        'COMP30020': 'COMP30020 - DP',
        'COMP30026': 'COMP30026 - MOC',
        'INFO20003': 'INFO20003 - DBS',
        }
}

# Merge settings_base and settings.
# If there is a clash in keys, we use the value in settings.
settings = defaultdict(lambda: None, {**_settings_base, **settings})
