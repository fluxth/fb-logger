import sqlite3

class LogDatabase():

	PATH = ''
	conn = None

	_USERS_SCHEMA = '''
		CREATE TABLE IF NOT EXISTS `users` (
			`id` integer unique primary key,
			`fbid` integer unique not null,
			`name` varchar(255) null,
			`username` varchar(255) null,
			`ts` datetime not null default (datetime('now', 'localtime'))
		);
	'''

	_LOGS_SCHEMA = '''
		CREATE TABLE IF NOT EXISTS `logs` (
			`id` integer unique primary key,
			`uid` integer not null,
			`ts` datetime not null default (datetime('now', 'localtime')),
			`lat` integer null,
			`p` integer null,
			`vc` integer null,
			`full` boolean not null default 0
		);
	'''

	_users = []

	def __init__(self, path):
		self.PATH = path
		self.connect()
		self.initialize()

	def connect(self):
		self.conn = sqlite3.connect(self.PATH)

	def initialize(self):
		c = self.conn.cursor()

		c.execute(self._LOGS_SCHEMA)
		c.execute(self._USERS_SCHEMA)

		self.conn.commit()

	def updateCachedUsers(self):
		c = self.conn.cursor()

		q = "SELECT `id`, `fbid` FROM `users` ORDER BY `id` ASC"
		c.execute(q)

		self._users = c.fetchall()

	def getUidByFbid(self, fbid):
		for user in self._users:
			if str(user[1]) == str(fbid):
				return user[0]
		return None

	def addUser(self, fbid):

		if self.getUidByFbid(fbid) is not None:
			return False

		c = self.conn.cursor()

		q = "INSERT INTO `users` (`fbid`) VALUES (:fbid)"
		c.execute(q, {
			'fbid': fbid,
		})

		uid = c.lastrowid
		self._users.append((uid, fbid))

		return uid

	def save(self, data, full=False):
		
		self.updateCachedUsers()

		for fbid in data:
			uid = self.getUidByFbid(fbid)

			if uid is None:
				uid = self.addUser(fbid)

			status = data[fbid]

			c = self.conn.cursor()
			q = '''
				INSERT OR IGNORE INTO `logs` (`uid`, `lat`, `p`, `vc`, `full`) 
				SELECT :uid, :lat, {p}, {vc}, :full 
				WHERE NOT EXISTS (
					SELECT 1 FROM `logs`
					WHERE `uid` = :uid AND `lat` = :lat AND `p` {pS} {p} AND `vc` {vcS} {vc}
				);
			'''.format(
				# Don't freak out yet, these are casted to ints.
				p = int(status['p']) if 'p' in status.keys() else 'NULL',
				vc = int(status['vc']) if 'vc' in status.keys() else 'NULL',
				pS = '=' if 'p' in status.keys() else 'IS',
				vcS = '=' if 'vc' in status.keys() else 'IS',
			)

			c.execute(q, {
				'uid': int(uid),
				'lat': int(status['lat']) if 'lat' in status else -2,
				'full': 1 if full else 0,
			})

		return self.conn.commit()

	def getUnnamedUsers(self):
		c = self.conn.cursor()

		q = "SELECT `fbid` from `users` WHERE `name` IS NULL ORDER BY `id` ASC;"
		c.execute(q)

		return [i[0] for i in c.fetchall()]
