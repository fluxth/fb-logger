import time
import os
import logging
import traceback

from fblogger.Scraper import BuddyList
from fblogger.Database import LogDatabase
from fblogger.Utils import load_config, tsprint, tserror, dprint, resolve_dict

from fblogger.Exceptions import (
    ContinueLoop, 
    LongPollReload, 
    NetworkError, 
    InvalidResponse, 
    DatabaseException
)

class LoggerApp():

    _VERSION = '1.3.2'

    CONFIG_PATH = ''

    config = None
    scraper = None
    db = None

    last_ping = 0

    errors = {
        'longpoll': {
            'NetworkError': 0,
            'InvalidResponse': 0,
        },
        'full': {
            'NetworkError': 0,
            'InvalidResponse': 0,
        }
    }

    def __init__(self, config_path='./config.json'):
        self.CONFIG_PATH = config_path
        self.initialize()

    def initialize(self):
        self.loadConfig()
        self.setupLogging()
        self.setupScraper()
        self.setupDatabase()

    def loadConfig(self):
        # Load config.json
        self.config = load_config(self.CONFIG_PATH)

    def getConfig(self, key, default=None):
        try:
            return resolve_dict(self.config, key)
        except (KeyError, ValueError):
            return default

    def setupLogging(self):
        # setup logging
        logging.basicConfig(
            filename=self.getConfig('log_file', './fblogger.log'), 
            format='[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%m/%d/%Y %I:%M:%S %p',
            level=logging.INFO)

        # write PID file
        with open(self.getConfig('pid_file', './fblogger.pid'), 'w') as f:
            f.write(str(os.getpid()))
        tsprint('FB Online-status Logger v{} started.'.format(self._VERSION))

    def setupScraper(self):
        self.scraper = BuddyList(
            c_user  = self.getConfig('credentials.c_user'), 
            xs      = self.getConfig('credentials.xs')
        )
        self.scraper.setConfig(self.getConfig('scraper'))

    def setupDatabase(self):
        self.db = LogDatabase(self.getConfig('database'))

    def getErrorCount(self, exc, mode):
        return self.errors[mode][exc.__class__.__name__]

    def incrementErrorCount(self, exc, mode):
        self.errors[mode][exc.__class__.__name__] += 1

    def resetErrorCounter(self, only_mode=None):
        for mode in self.errors:
            if only_mode is not None:
                if mode != only_mode:
                    continue

            for exc in self.errors[mode]:
                self.errors[mode][exc] = 0

        return True

    def handleFullRequestException(self, exc, reset_threshold=False):
        self.incrementErrorCount(exc, 'full')

        logging.error(exc, exc_info=True)
        tserror('FullRequest {}: {}'.format(exc.__class__.__name__, exc))

        err_count = self.getErrorCount(exc, 'full')
        if err_count > self.getConfig('scraper.request_retry_limit', 3):
            if err_count > self.getConfig('scraper.longpoll_chill_limit', 6):
                # Fatal error, exit program
                tsprint('Chill limit reached after {} retries, retry aborted.'.format(err_count))
                raise Exception('Maximum retry threshold reached.')

            wait = self.getConfig('scraper.request_chill_timeout', 120)
            tsprint('FullRequest chill threshold reached after {} retries.'.format(err_count))
        else:
            wait = self.getConfig('scraper.request_retry_timeout', 30)

        tsprint('Waiting {}s before retrying FullRequest ({})...'.format(wait, err_count))
        time.sleep(wait)

        # threshold then reset session
        if reset_threshold is not False and err_count > reset_threshold:
            tsprint('Session reset after {} retries.'.format(err_count))
            self.scraper.resetSession()

        raise ContinueLoop

    def handleLongpollException(self, exc):
        self.incrementErrorCount(exc, 'longpoll')

        logging.error(exc, exc_info=True)
        tserror('Longpoll {}: {}'.format(exc.__class__.__name__, exc))

        err_count = self.getErrorCount(exc, 'longpoll')
        if err_count > self.getConfig('scraper.longpoll_retry_limit', 3):
            if err_count > self.getConfig('scraper.longpoll_chill_limit', 6):
                # Exit to full request loop
                tsprint('Chill limit reached after {} retries, exiting longpoll mode.'.format(err_count))
                raise exc

            wait = self.getConfig('scraper.longpoll_chill_timeout', 60)
            tsprint('Longpoll chill threshold reached after {} retries.'.format(err_count))
        else:
            wait = self.getConfig('scraper.longpoll_retry_timeout', 10)

        tsprint('Waiting {}s before retrying longpoll ({})...'.format(wait, err_count))
        time.sleep(wait)
        
        raise ContinueLoop

    def ping(self):
        if time.time() - self.last_ping > self.getConfig('ping_interval', 300):
            self.db.ping()
            self.last_ping = time.time()

        return

    def mainLoop(self):
        while True:
            try:
                dprint('Initial GET request')

                self.ping()

                resp = self.scraper.getBuddyList()
                chatproxy, overlay = self.scraper.parseFbResponse(resp)
                    
                # reset error counter then save response
                self.resetErrorCounter(only_mode='full')
                
                self.scraper.saveToDB(chatproxy, overlay, self.db, full=True)

                # Longpoll not enabled
                if self.getConfig('scraper.longpoll', True) is not True:
                    req_wait = self.getConfig('scraper.request_interval', 300)
                    time.sleep(req_wait)

                    chatproxy = None
                    overlay = None

                    continue

                seq = 2
            
                while True:
                    if 'seq' in resp.keys():
                        seq = resp['seq']

                    chatproxy = None
                    overlay = None

                    self.ping()

                    try:
                        dprint('Polling seq={}'.format(seq))
                        resp = self.scraper.longPoll(seq)


                    # handle failed polling
                    except NetworkError as exc:
                        try:
                            self.handleLongpollException(exc)
                        except ContinueLoop:
                            continue

                    except InvalidResponse as exc:
                        try:
                            self.handleLongpollException(exc)
                        except ContinueLoop:
                            continue


                    # reset error counter then handle response 
                    self.resetErrorCounter(only_mode='longpoll')
                    if resp['t'] == 'heartbeat':
                        dprint('Longpoll seq={} heartbeat.'.format(seq))

                    elif resp['t'] == 'lb':
                        tsprint('Got "lb" on longpoll seq={}, applying then reloading...'.format(seq))
                        self.scraper.updateLoadBalancerInfo(self.scraper.parseLoadBalancerInfo(resp))
                        raise LongPollReload('Got lb from longpoll packet.')

                    elif resp['t'] == 'fullReload':
                        dprint('Longpoll seq={} returned fullReload, try saving then reloading.'.format(seq))
                        chatproxy, overlay = self.scraper.parseFbResponse(resp)
                        # dict_merge(flist, fb.parseFbResponse(resp))

                        raise LongPollReload('Got fullReload from longpoll packet.')

                    elif resp['t'] == 'msg':
                        chatproxy, overlay = self.scraper.parseFbResponse(resp)

                    else:
                        raise LongPollReload('Got unknown packet type "{}".'.format(resp['t']))

                    # save data
                    if chatproxy is not None or overlay is not None:
                        self.scraper.saveToDB(chatproxy, overlay, self.db)


                    # Limit loop to set frequency
                    time.sleep(int(1 / self.getConfig('scraper.loop_frequency', 10)))


            except LongPollReload as m:
                tsprint('Longpoll Reload: {}'.format(m))
                self.scraper.resetSession()
                continue

            except NetworkError as exc:
                try:
                    self.handleFullRequestException(
                        exc, 
                        reset_threshold=self.getConfig('scraper.request_session_limit', 2)
                    )
                except ContinueLoop:
                    continue

            except InvalidResponse as exc:
                try:
                    self.handleFullRequestException(
                        exc,
                        reset_threshold=self.getConfig('scraper.request_session_limit', 2)
                    )
                except ContinueLoop:
                    continue

            except ContinueLoop:
                continue

    def run(self):
        try:
            self.mainLoop()
        except KeyboardInterrupt:
            tsprint('User Quit')
        except DatabaseException as e:
            logging.fatal(e, exc_info=True)
            tserror('Database Error: {}'.format(e))
            traceback.print_tb(e.__traceback__)
        except Exception as e:
            logging.fatal(e, exc_info=True)
            tserror('FATAL: {}'.format(e))
            traceback.print_tb(e.__traceback__)
        finally:
            tsprint('Terminating...')

            # Delete PID file
            os.remove(self.getConfig('pid_file', './fblogger.pid'))

