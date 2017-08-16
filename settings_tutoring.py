import os

from collections import defaultdict

settings = defaultdict(lambda: None, {
    'username': 'dsporteous',
    'password': os.environ['UNIMELBPASSTUTOR'],
    'media_type': 'v',
    'subject_choices': '',
    'date_range': '3-12',
})
