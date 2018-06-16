#!/usr/bin/env python3

# -------------------------------
# inject_fbinfo.py - v1.0.0
#
# This script injects your friend's name on Facebook to the database.
# The access token needs to be able to access "real" user ID on FB.
# Newer FB apps cannot do this, the app needs to be somewhat old.
# Facebook's Graph Explorer App can do this. So it is preferred. 
# -------------------------------

from fblogger.Utils import load_config
from fblogger.Database import LogDatabase

import requests
from urllib.parse import urlencode

# Load config.json
config = load_config('./config.json')
db = LogDatabase(config['database'])

print('Inject user info to DB tool\n')

print('Obtain your access token from Graph Explorer app.')
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
		data.update(resp.json())

		# print(data)

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
