import sqlite3
import os
from enum import Enum

from fblogger.Utils import tsprint

class LogType(Enum):
    UNKNOWN = 0
    CHATPROXY_LONGPOLL = 1
    CHATPROXY_RELOAD = 2
    BUDDYLIST_OVERLAY = 3

class LogDatabase():

    config = None
    conn = None

    SCHEMA_VERSION = 2

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
            `type` integer not null default 0
        );
    '''

    _PINGS_SCHEMA = '''
        CREATE TABLE IF NOT EXISTS `pings` (
            `ts` timestamp unique primary key not null default (strftime('%s', 'now'))
        );
    '''

    _DBCONFIG_SCHEMA = '''
        CREATE TABLE IF NOT EXISTS `dbconfig` (
            `key` varchar(255) unique primary key not null,
            `value` text null
        );
    '''

    _users = []

    def __init__(self, config, *args, **kwargs):
        self.config = config
        self.connect(*args, **kwargs)
        self.initialize()

    def connect(self, *args, **kwargs):
        self.conn = sqlite3.connect(self.config.get('path', './fblogger.db'), *args, **kwargs)

    def initialize(self):
        c = self.conn.cursor()

        c.execute(self._LOGS_SCHEMA)
        c.execute(self._USERS_SCHEMA)
        c.execute(self._DBCONFIG_SCHEMA)

        self.checkDbConfig()

        self.conn.commit()

    def getDbConfig(self, key):
        c = self.conn.cursor()

        q = "SELECT `value` FROM `dbconfig` WHERE `key` = :key LIMIT 1;"
        c.execute(q, {
            'key': key
        })

        data = c.fetchall()
        if len(data) > 0:
            return data[0][0]
        else:
            raise KeyError('Key {} not found in DBConfig'.format(key))

    def setDbConfig(self, key, value):
        c = self.conn.cursor()
        
        q = "INSERT OR REPLACE INTO `dbconfig` (`key`, `value`) VALUES (:key, :value)"
        c.execute(q, {
            'key': key,
            'value': str(value),
        })

        return True if c.rowcount == 1 else False

    def checkDbConfig(self):
        self.checkSchemaUpdates()

    def checkSchemaUpdates(self):
        try:
            sc_ver = int(self.getDbConfig('schema_version'))
        except KeyError:
            tsprint('DB schema version not found, assuming freshly installed database...')
            sc_ver = self.SCHEMA_VERSION
            self.setDbConfig('schema_version', sc_ver)

        if sc_ver < self.SCHEMA_VERSION:
            # Update schema
            tsprint('Updating database schema from v{} to v{}...'.format(sc_ver, self.SCHEMA_VERSION))
            self.migrateSchema(self.SCHEMA_VERSION)
        else:
            tsprint('Database schema up-to-date.')

        return

    def migrateSchema(self, to_version):
        migrations_path = self.config.get('migrations', './fblogger/migrations/')
        migration_filename = 'migration_v{}.sql'

        sc_ver = int(self.getDbConfig('schema_version'))

        if sc_ver >= to_version:
            raise MigrationException('Cannot migrate to current or older schema.')

        c = self.conn.cursor()
        retries = 0
        while sc_ver < to_version:
            if retries >= 3:
                raise MigrationException('Migration took too many retries to update from v{} to v{}.'.format(sc_ver, next_ver))

            next_ver = sc_ver + 1
            tsprint('Migrating to schema v{}...'.format(next_ver))

            target_migration = os.path.join(migrations_path, migration_filename.format(next_ver))
            if not os.path.isfile(target_migration):
                raise MigrationException('Migration for schema version {} not found: {}'.format(next_ver, target_migration))

            with open(target_migration, 'r') as f:
                sql = f.read()
                c.executescript(sql)

            self.conn.commit()
            sc_ver = int(self.getDbConfig('schema_version'))

            if sc_ver < next_ver:
                retries += 1
            else:
                retries = 0

        tsprint('Database schema successfully migrated to v{}.'.format(to_version))
        return

    def updateCachedUsers(self):
        c = self.conn.cursor()

        q = "SELECT `id`, `fbid` FROM `users` ORDER BY `id` ASC;"
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

        q = "INSERT INTO `users` (`fbid`) VALUES (:fbid);"
        c.execute(q, {
            'fbid': fbid,
        })

        uid = c.lastrowid
        self._users.append((uid, fbid))

        return uid

    def save(self, data, logtype=0):
        
        self.updateCachedUsers()

        for fbid in data:
            uid = self.getUidByFbid(fbid)

            if uid is None:
                uid = self.addUser(fbid)

            status = data[fbid]

            c = self.conn.cursor()
            q = '''
                INSERT OR IGNORE INTO `logs` (`uid`, `lat`, `p`, `vc`, `type`) 
                SELECT :uid, :lat, {p}, {vc}, :type 
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
                'type': int(logtype),
            })

        return self.conn.commit()

    def ping(self):
        c = self.conn.cursor()

        q = 'INSERT OR IGNORE INTO `pings` DEFAULT VALUES;'
        c.execute(q)

        return c.lastrowid

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
            ORDER BY `l`.`lat` DESC;
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
            LIMIT 1;
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
            ORDER BY `l`.`id` DESC
            LIMIT 100;
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
            'type': i[6],
        } for i in c.fetchall()]

    def getTimelinePlotData(self, user_id, start):
        c = self.conn.cursor()

        q = """
            SELECT `l`.`ts`, `l`.`p`, `l`.`type`
            FROM `logs` AS `l`
            WHERE `l`.`uid` = :uid AND `l`.`lat` >= :start AND `l`.`lat` <= :end
            ORDER BY `l`.`id` ASC;
        """
        c.execute(q, {
            'uid': user_id,
            'start': start,
            'end': start + 86400
        })

        return [[int(i[0] - start), i[1], i[2]] for i in c.fetchall()]

        

# Exceptions
class DatabaseException(Exception):
    pass

class MigrationException(DatabaseException):
    pass
