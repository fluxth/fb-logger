import random
import time
import json
import requests

from urllib.parse import urlencode

from fblogger.Utils import tsprint, dprint

class BuddyList:

    URL = 'https://{}-edge-chat.facebook.com/pull'

    initialzed = False

    lb_id = 0
    client_id = 0

    c_user = None
    xs = None

    session = None
    config = {
        "cache_lb": False,
        "request_timeout": 20,
        "sticky_expire": 1800,
    }

    lb_data = None
    lb_timestamp = 0

    def __init__(self, c_user=None, xs=None):
        self.setCredentials(c_user, xs)
        self.initializeSession()
        self.initialzed = True

    def setConfig(self, config):
        self.config.update(config)

    def setCredentials(self, c_user, xs):
        self.c_user = c_user
        self.xs = xs

    def setLoadBalancerId(self, lb_id=None):
        if lb_id is not None:
            self.lb_id = lb_id
        else:
            # Randomized ID [0 to 6]
            self.lb_id = random.randint(0, 6)

    def setClientId(self, client_id=None):
        if client_id is not None:
            self.client_id = client_id
        else:
            # Randomized 8-digit HEX
            self.client_id = '%08x' % random.randrange(16**8)

    def initializeSession(self):
        self.session = requests.Session()

        self.session.cookies.set('c_user', self.c_user, domain='.facebook.com')
        self.session.cookies.set('xs', self.xs, domain='.facebook.com')

        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36'})
        self.session.headers.update({'Accept-Encoding': 'identity, gzip'})
        self.session.headers.update({'Origin': 'https://www.facebook.com'})
        self.session.headers.update({'Referer': 'https://www.facebook.com/'})

        self.setLoadBalancerId()
        self.setClientId()

    def resetSession(self):
        self.lb_id = None
        self.client_id = None

        self.initializeSession()

    def getEndpointUrl(self):
        return self.URL.format(self.lb_id)

    def parseJsonpResponse(self, resp):
        return resp.replace('for (;;); ', '')

    def doRequest(self, url, qs, timeout=None):

        if self.initialzed is not True:
            raise NotInitialized('BuddyList is not correctly initialzed.')

        req = requests.Request('GET', '{}?{}'.format(url, urlencode(qs)))
        prep = self.session.prepare_request(req)

        timeout = self.config['request_timeout'] if timeout is None else timeout

        try:
            resp = self.session.send(prep, timeout=timeout)
        except requests.exceptions.ReadTimeout as m:
            raise NetworkError('HTTP Read Timeout ({})'.format(m))

        resp.raise_for_status()

        return resp.text

    def doFbRequest(self, url, qs):
        data = self.parseJsonpResponse(self.doRequest(url, qs))
        return json.loads(data)

    def doLongPoll(self, url, qs, timeout):
        data = self.parseJsonpResponse(self.doRequest(url, qs, timeout))
        return json.loads(data)

    def checkLoadBalancerInfo(self):
        if self.lb_data is None or self.config['cache_lb'] is not True:
            self.updateLoadBalancerInfo()

        if time.time() - self.lb_timestamp > self.config['sticky_expire']:
            self.updateLoadBalancerInfo()
            raise LongPollReload('Sticky cookie expired.')

    def updateLoadBalancerInfo(self):
            self.lb_data = self.getLoadBalancerInfo()
            self.lb_timestamp = time.time()

    def getLoadBalancerInfo(self):

        url = self.getEndpointUrl()
        qs = {
            'clientid': self.client_id,
            'channel': 'p_{}'.format(self.c_user),
            'seq': 0,
            'partition': -2,
            'cb': 'dead',
            'idle': 1,
            'qp': 'y',
            'cap': 8,
            'pws': 'fresh',
            'isq': 254579,
            'msgs_recv': 0,
            'uid': self.c_user,
            'viewer_uid': self.c_user,
            'state': 'active'
        }

        data = self.doFbRequest(url, qs)

        if data['t'] != 'lb':
            raise InvalidResponse('Expected packet type "lb" from getLoadBalancerInfo.')
            return False

        if 'lb_info' not in data.keys():
            raise InvalidResponse('Expected packet payload "lb_info" from getLoadBalancerInfo.')
            return False

        return data['lb_info']

    def getBuddyList(self):

        self.checkLoadBalancerInfo()

        url = self.getEndpointUrl()
        qs = {
            'clientid': self.client_id,
            'channel': 'p_{}'.format(self.c_user),
            'seq': 1,
            'partition': -2,
            'cb': 'dead',
            'idle': 1,
            'qp': 'y',
            'cap': 8,
            'pws': 'fresh',
            'isq': 254579,
            'msgs_recv': 1,
            'uid': self.c_user,
            'viewer_uid': self.c_user,
            'state': 'active',
            'sticky_token': self.lb_data['sticky'],
            'sticky_pool': self.lb_data['pool']
        }

        data = self.doFbRequest(url, qs)

        if data['t'] != 'fullReload':
            raise InvalidResponse('Expected packet type "fullReload" from getBuddyList, got "{}"'.format(data['t']))

        return data

    # Currently 'idle' (actual status on fb) time not implemented
    def longPoll(self, seq, idle=1002):

        self.checkLoadBalancerInfo()

        url = self.getEndpointUrl()
        qs = {
            'clientid': self.client_id,
            'channel': 'p_{}'.format(self.c_user),
            'seq': seq,
            'partition': -2,
            'cb': 'dead',
            'idle': idle,
            'qp': 'y',
            'cap': 8,
            'pws': 'fresh',
            'isq': 254579,
            'msgs_recv': seq,
            'uid': self.c_user,
            'viewer_uid': self.c_user,
            'state': 'active',
            'sticky_token': self.lb_data['sticky'],
            'sticky_pool': self.lb_data['pool']
        }

        return self.doLongPoll(url, qs, 700) 

    def parseFbResponse(self, resp):
        if 'ms' not in resp.keys():
            raise InvalidResponse('"ms" not found when parsing.')
            return False

        for item in resp['ms']:
            if item['type'] == 'chatproxy-presence':
                if 'buddyList' not in item.keys():
                    raise InvalidResponse('"buddyList" not found in "chatproxy-presence" when parsing.')
                    return False
                return item['buddyList']

            dprint(item)

        return None

    def saveToDB(self, parsed, db, full=False):
        if parsed is None:
            # nothing to save
            return False

        self.printActiveUsers(parsed)
        return db.save(parsed, full=full)

    def printActiveUsers(self, data):
        total = len(data)
        active = 0
        idle = 0
        
        for fbid in data:
            if 'p' not in data[fbid].keys():
                continue

            status = data[fbid]['p']
            if status == 2:
                active += 1
            if status == 0:
                idle += 1

        tsprint('{} active, {} idle, {} total.'.format(active, idle, total))


# Exceptions

class BuddyListException(Exception):
    pass

class NotInitialized(BuddyListException):
    pass

class NetworkError(BuddyListException):
    pass

class InvalidResponse(BuddyListException):
    pass

class LongPollReload(BuddyListException):
    pass


