#!/usr/bin/python
import sys

# Path to venv
sys.path.insert(0,"/opt/privacyidea/venv/lib/python3.9/site-packages")

import os, flask
cur_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(cur_dir)
sys.path.insert(0, cur_dir)

sys.stdout = sys.stderr
from privacyidea.app import create_app

# Now we can select the config file:
application = create_app(config_name="production", config_file="/etc/privacyidea/pi.cfg")
