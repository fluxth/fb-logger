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
            `ts` timestamp not null default (strftime('%s', 'now'))
        );
    '''

    _LOGS_SCHEMA = '''
        CREATE TABLE IF NOT EXISTS `logs` (
            `id` integer unique primary key,
            `uid` integer not null,
            `ts` timestamp not null default (strftime('%s', 'now')),
            `lat` integer null,
            `p` integer null,
            `vc` integer null,
            `full` boolean not null default 0
        );
    '''

    _users = []

    def __init__(self, path, *args, **kwargs):
        self.PATH = path
        self.connect(*args, **kwargs)
        self.initialize()

    def connect(self, *args, **kwargs):
        self.conn = sqlite3.connect(self.PATH, *args, **kwargs)

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

    def listUsers(self):
        c = self.conn.cursor()

        # q = """
        #     SELECT DISTINCT `u`.`id`, `u`.`fbid`, `u`.`name`, `l`.`lat`, `l`.`p`, `l`.`ts`
        #     from `logs` AS `l`
        #     INNER JOIN `users` AS `u` ON `u`.`id` = `l`.`uid`
        #     ORDER BY `u`.`id` DESC
        # """
        q = """
            SELECT `u`.`id`, `u`.`fbid`, `u`.`name`, `l`.`lat`, `l`.`p`, `l`.`ts`
            FROM `users` AS `u`
            LEFT OUTER JOIN `logs` AS `l` ON `u`.`id` = `l`.`uid`
            WHERE `l`.`id` IN (SELECT MAX(`id`) FROM `logs` GROUP BY `uid`)
            ORDER BY `l`.`lat` DESC
        """
        c.execute(q)

        return [{
            'id': i[0],
            'fbid': i[1],
            'name': i[2],
            'last_active': i[3],
            'status': i[4],
            'recorded': i[5],
        } for i in c.fetchall()]

    def getUser(self, user_id):
        c = self.conn.cursor()

        q = """
            SELECT *
            FROM `users` AS `u`
            WHERE `u`.`id` = :uid
            LIMIT 1
        """
        c.execute(q, {
            'uid': user_id
        })

        u = c.fetchall()[0]

        return {
            'id': u[0],
            'fbid': u[1],
            'name': u[2],
            'username': u[3],
            'added': u[4],
        }

    def getUserActivities(self, user_id):
        c = self.conn.cursor()

        q = """
            SELECT *
            FROM `logs` AS `l`
            WHERE `l`.`uid` = :uid
            ORDER BY `l`.`ts` DESC
        """
        c.execute(q, {
            'uid': user_id
        })

        return [{
            'id': i[0],
            'recorded': i[2],
            'lat': i[3],
            'p': i[4],
            'vc': i[5],
            'full': i[6],
        } for i in c.fetchall()]



