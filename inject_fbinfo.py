#!/usr/bin/env python3

# -------------------------------
# inject_fbinfo.py - v1.0.0
#
# This script injects your friend's name on Facebook to the database.
# The access token needs to be able to access "real" user ID on FB.
# Newer FB apps cannot do this, the app needs to be somewhat old.
# Since Facebook Graph Explorer App is deprecated, you can use any other older apps.
# The URL below is from Spotify's app, use Chrome Dev tool to intercept the token.
#
# https://www.facebook.com/v2.3/dialog/oauth?client_id=174829003346&response_type=token&state=0&redirect_uri=https%3A%2F%2Faccounts.spotify.com%2Fapi%2Ffacebook%2Foauth%2Faccess_token
# -------------------------------

from fblogger.Utils import load_config
from fblogger.Database import LogDatabase

import requests
from urllib.parse import urlencode

# Load config.json
config = load_config('./config.json')
db = LogDatabase(config['database'])

print('Inject user info to DB tool\n')

print('Obtain your access token from Graph Explorer or older app.')
print('Read the README file or this tool\'s source code to learn more.')
token = input('Enter FB token > ')

URL = 'https://graph.facebook.com/v2.6/?{qs}'
qs = {
    'fields': 'name',
    'access_token': token
}

users = db.getUnnamedUsers()
processed = []

data = {}

CHUNK = 20

c = db.conn.cursor()
try:
    x = 0
    while x < len(users):

        sel = users[x:CHUNK+x]
        uids = [str(u) for u in sel]

        qs['ids'] = ','.join(uids)

        print('\nObtaining batch {}, {} users total...'.format(x+CHUNK, len(users)))

        resp = requests.get(URL.format(qs=urlencode(qs)))
        data = resp.json()

        x += len(sel)

        if 'error' in data.keys():
            print('An error occurred, skipping this batch.')
            print(data)
            continue

        for fbid in data:
            user = data[fbid]

            q = "UPDATE `users` SET `name` = ? WHERE `fbid` = ?"
            c.execute(q, (user['name'], int(user['id'])))

            print('{} > {}'.format(user['id'], user['name']))

            processed.append(int(user['id']))

    skipped = [item for item in users if item not in processed]

    if len(skipped) > 0:
        print('\n[*] There are {} users not processed:'.format(len(skipped)))
        for u in skipped:
            print('- {}'.format(u))

except KeyboardInterrupt:
    print('QUIT')
finally:
    db.conn.commit()
