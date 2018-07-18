#!/usr/bin/env python3

# -------------------------------
# last_active.py - v1.0.0
#
# -------------------------------

from fblogger.Utils import load_config
from fblogger.Database import LogDatabase

from datetime import datetime

# Load config.json
config = load_config('./config.json')
db = LogDatabase(config['database'])

print('Friend\'s last active times.\n')

def strfdelta(tdelta, fmt):
    d = {"days": tdelta.days}
    d["hours"], rem = divmod(tdelta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    return fmt.format(**d)

def humantimeago(time):
    la = datetime.fromtimestamp(time)
    delta = datetime.now() - la
    return '{} ago'.format(strfdelta(delta, '{days}d, {hours}h {minutes}m'))

for user in db.listUsers():
    print('{} {}: last active {}'.format(
        user['name'] if user['name'] is not None else user['fbid'],
        user['fbid'],
        (
            'now' if user['status'] == 2 else (
                'none' if user['last_active'] == -1 else humantimeago(user['last_active'])
            )
        ),
    ))
