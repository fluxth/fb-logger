import random
import time
import json
import requests
import logging

from urllib.parse import urlencode

from fblogger.Utils import tsprint, dprint, resolve_dict
from fblogger.Database import LogType


class BuddyList():

    URL = 'https://{}-edge-chat.facebook.com/pull'

    initialized = False

    lb_id = 0
    client_id = 0

    c_user = None
    xs = None

    session = None
    config = {
        "cache_lb": False,
        "sticky_expire": 1800,

        "request_timeout": 20,
    }

    lb_data = None
    lb_timestamp = 0

    def __init__(self, c_user=None, xs=None):
        self.setCredentials(c_user, xs)

    def setConfig(self, config):
        self.config.update(config)

    def getConfig(self, key, default=None):
        try:
            return resolve_dict(self.config, key)
        except (KeyError, ValueError):
            return default

    def setCredentials(self, c_user, xs):
        self.c_user = c_user
        self.xs = xs

        if self.c_user is not None and self.xs is not None:
            self.initializeSession()

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

        self.initialized = True

    def resetSession(self):
        self.lb_id = None
        self.client_id = None

        self.initializeSession()

    def getEndpointUrl(self):
        return self.URL.format(self.lb_id)

    def sanitizeJsonResponse(self, resp):
        return resp.replace('for (;;); ', '')

    def doRequest(self, url, qs, timeout=None):

        if self.initialized is not True:
            raise NotInitialized('BuddyList is not correctly initialized.')

        req = requests.Request('GET', '{}?{}'.format(url, urlencode(qs)))
        prep = self.session.prepare_request(req)

        timeout = self.getConfig('request_timeout', 20) if timeout is None else timeout

        try:
            resp = self.session.send(prep, timeout=timeout)
        except requests.exceptions.ReadTimeout as m:
            logging.error(m, exc_info=True)
            raise NetworkError('HTTP Read Timeout ({})'.format(m))
        except requests.exceptions.ConnectionError as m:
            logging.error(m, exc_info=True)
            raise NetworkError('Connection Error ({})'.format(m))

        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as m:
            logging.error(m, exc_info=True)
            raise NetworkError('HTTP Error ({})'.format(m))

        return resp.text

    def doFbRequest(self, url, qs):
        data = self.sanitizeJsonResponse(self.doRequest(url, qs))
        return json.loads(data)

    def doLongPoll(self, url, qs, timeout):
        data = self.sanitizeJsonResponse(self.doRequest(url, qs, timeout))
        return json.loads(data)

    def checkLoadBalancerInfo(self):
        if self.lb_data is None or self.getConfig('cache_lb') is False:
            self.updateLoadBalancerInfo()

        if time.time() - self.lb_timestamp > self.getConfig('sticky_expire', 1800):
            self.updateLoadBalancerInfo()
            raise LongPollReload('Sticky cookie expired.')

    def updateLoadBalancerInfo(self, lb_info=None):
            if lb_info is not None:
                self.lb_data = lb_info

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
        return self.parseLoadBalancerInfo(data)

    def parseLoadBalancerInfo(self, data):
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

        if data['t'] == 'lb':
            tsprint('Got "lb" on fullreload, applying then reconnecting...')
            self.updateLoadBalancerInfo(self.parseLoadBalancerInfo(data))
            raise ContinueLoop

        if data['t'] != 'fullReload':
            logging.info('msg on fullreload: {}'.format(data))
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

        return self.doLongPoll(url, qs, self.getConfig('longpoll_timeout', 700)) 

    def parseFbResponse(self, resp):
        if 'ms' not in resp.keys():
            raise InvalidResponse('"ms" not found when parsing.')
            return False

        chatproxy = None
        overlay = None

        for item in resp['ms']:
            if item['type'] == 'chatproxy-presence':
                if 'buddyList' not in item.keys():
                    raise InvalidResponse('"buddyList" not found in "chatproxy-presence" when parsing.')
                    chatproxy = False

                chatproxy = item['buddyList']

            if item['type'] == 'buddylist_overlay':
                if 'overlay' not in item.keys():
                    raise InvalidResponse('"overlay" not found in "buddylist_overlay" when parsing.')
                    overlay = False

                overlay = item['overlay']

            if chatproxy is None and overlay is None:
                dprint(item)
                return (None, None)

        return (chatproxy, overlay)

    # Normalizes buddylist_overlay to chatproxy-presence's format
    def normalizeOverlayResponse(self, resp):
        output = {}
        for u, data in resp.items():
            output[u] = {}
            if 'a' in data:
                output[u]['p'] = data['a']
            if 'la' in data:
                output[u]['lat'] = data['la']
            if 'vc' in data:
                output[u]['vc'] = data['vc']

        return output

    def saveToDB(self, proxy, overlay, db, full=False):
        if proxy is not None:
            logtype = LogType.CHATPROXY_RELOAD if full else LogType.CHATPROXY_LONGPOLL

            self.printActiveUsers(proxy, full=full)
            db.save(proxy, logtype=logtype.value)

        if overlay is not None:
            logtype = LogType.BUDDYLIST_OVERLAY

            for fbid in overlay:
                tsprint('Overlay: User {} went {}'.format(fbid, 'online' if overlay[fbid]['a'] == 2 else 'offline'))
            db.save(self.normalizeOverlayResponse(overlay), logtype=logtype.value)

        return

    def printActiveUsers(self, data, full=False):
        # Update text and mechanism to calculate, currently not correct data

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

        mode = 'Full' if full else 'Longpoll'

        tsprint('ChatProxy [{}]: {} active, {} idle, {} total.'.format(mode, active, idle, total))


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


