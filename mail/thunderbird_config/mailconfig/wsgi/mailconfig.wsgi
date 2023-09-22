#!/usr/bin/python3
import sys
import os

os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'

# Path to venv
sys.path.insert(0,"/opt/mail/mailconfig/wsgi/lib/python3.9/site-packages")

import os, bottle
cur_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(cur_dir)
sys.path.insert(0, cur_dir)
app_name = os.path.basename(__file__).split('.')[0]
app = __import__(app_name)  # This loads the application
application = bottle.default_app()
