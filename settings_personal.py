import os

from collections import defaultdict

settings = defaultdict(lambda: None, {
    'username': 'porteousd',
    'password': os.environ['UNIMELBPASS'],
    'media_type': 'v',
    'subject_choices': '',
    'date_range': '3-12',
})
