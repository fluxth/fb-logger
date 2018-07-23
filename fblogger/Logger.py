import time
import sys
import os
import logging
import traceback

from fblogger.Scraper import BuddyList, LongPollReload, NetworkError, InvalidResponse
from fblogger.Database import LogDatabase
from fblogger.Utils import load_config, tsprint, dprint, resolve_dict

class LoggerApp():

    _VERSION = '1.0.0'

    CONFIG_PATH = ''

    config = None
    scraper = None
    db = None

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
        except ValueError:
            return default

    def setupLogging(self):
        # setup logging
        logging.basicConfig(
            filename=self.getConfig('log_file', './fblogger.log'), 
            format='[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%m/%d/%Y %I:%M:%S %p',
            level=logging.DEBUG)

        # write PID file
        with open(self.getConfig('pid_file', './fblogger.pid'), 'w') as f:
            f.write(str(os.getpid()))
        tsprint('Logging started.')

    def setupScraper(self):
        self.scraper = BuddyList(
            c_user  = self.getConfig('credentials.c_user'), 
            xs      = self.getConfig('credentials.xs')
        )
        self.scraper.setConfig(self.getConfig('scraper'))

    def setupDatabase(self):
        self.db = LogDatabase(self.getConfig('database'))

    def mainLoop(self):
        while True:
            try:
                dprint('Initial GET request')

                blist = self.scraper.getBuddyList()
                flist = self.scraper.parseFbResponse(blist)
                self.scraper.saveToDB(flist, self.db, full=True)

                seq = 2
            
                while True:
                    if 'seq' in blist.keys():
                        seq = blist['seq']

                    flist = None

                    try:
                        dprint('Polling seq={}'.format(seq))
                        blist = self.scraper.longPoll(seq)


                    # handle failed polling
                    except NetworkError as m:
                        logging.error(m, exc_info=True)
                        tsprint('Longpoll Network Error: {}'.format(m))
                        
                        # Replace with config values
                        time.sleep(10)
                        continue

                        # threshold then raise another exception to reload

                    except InvalidResponse as m:
                        logging.error(m, exc_info=True)
                        tsprint('Longpoll Invalid Response: {}'.format(m))
                        
                        # Replace with config values
                        time.sleep(10)
                        continue

                        # threshold then raise another exception to reload


                    # handle response 
                    if blist['t'] == 'heartbeat':
                        dprint('Longpoll seq={} heartbeat.'.format(seq))

                    elif blist['t'] == 'fullReload':
                        dprint('Longpoll seq={} returned fullReload, try saving then reload.'.format(seq))
                        flist = self.scraper.parseFbResponse(blist)
                        # dict_merge(flist, fb.parseFbResponse(blist))

                        raise LongPollReload('Got fullReload from longpoll packet.')

                    elif blist['t'] == 'msg':
                        flist = self.scraper.parseFbResponse(blist)

                    else:
                        raise LongPollReload('Got unknown packet type "{}".'.format(blist['t']))

                    # save data
                    if flist is not None:
                        self.scraper.saveToDB(flist, self.db)


                    # Replace with config values
                    time.sleep(0.1)


            except LongPollReload as m:
                tsprint('Longpoll Reload: {}'.format(m))
                self.scraper.resetSession()
                continue

            except NetworkError as m:
                # TODO: Implement "chill" timeout
                wait = self.getConfig('scraper.retry_timeout', 30)

                logging.error(m, exc_info=True)
                tsprint('Network Error: {}, trying again in {}s'.format(m, wait))

                time.sleep(wait)

                # threshold then reset session
                # self.scraper.resetSession()
                continue

            except InvalidResponse as m:
                # TODO: Implement "chill" timeout
                wait = self.getConfig('scraper.retry_timeout', 30)

                logging.error(m, exc_info=True)
                tsprint('Invalid Response: {}, trying again in {}s'.format(m, wait))

                time.sleep(wait)

                self.scraper.resetSession()
                continue

    def run(self):
        try:
            self.mainLoop()
        except KeyboardInterrupt:
            tsprint('User Quit')
        except Exception as e:
            logging.fatal(e, exc_info=True)
            traceback.print_tb(e.__traceback__)
        finally:
            tsprint('Terminating...')

            # Delete PID file
            os.remove(self.getConfig('pid_file', './fblogger.pid'))

            sys.exit(0)
