import time
import sys
import os
import logging

from fblogger.Scraper import BuddyList, LongPollReload, NetworkError
from fblogger.Database import LogDatabase
from fblogger.Utils import load_config, tsprint, dprint

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

    def setupLogging(self):
        # setup logging
        logging.basicConfig(
            filename=self.config['log_file'] if 'log_file' in self.config.keys() else './fblogger.log', 
            format='[%(asctime)s] %(levelname)s: %(message)s',
            datefmt='%m/%d/%Y %I:%M:%S %p',
            level=logging.DEBUG)

        # write PID file
        with open(self.config['pid_file'] if 'pid_file' in self.config.keys() else './fblogger.pid', 'w') as f:
            f.write(str(os.getpid()))
        tsprint('Logging started.')

    def setupScraper(self):
        self.scraper = BuddyList(
            c_user  = self.config['credentials']['c_user'], 
            xs      = self.config['credentials']['xs']
        )
        self.scraper.setConfig(self.config['scraper'])

    def setupDatabase(self):
        self.db = LogDatabase(self.config['database'])

    def mainLoop(self):
        while True:
            dprint('Initial GET request')

            blist = self.scraper.getBuddyList()
            flist = self.scraper.parseFbResponse(blist)
            self.scraper.saveToDB(flist, self.db, full=True)

            seq = 2
            try:
                while True:
                    if 'seq' in blist.keys():
                        seq = blist['seq']

                    flist = None

                    try:
                        dprint('Polling seq={}'.format(seq))
                        blist = self.scraper.longPoll(seq)

                    # handle failed polling
                    except NetworkError as m:
                        tsprint('Network Error: {}'.format(m))
                        
                        # Replace with config values
                        time.sleep(10)
                        continue

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

                    if flist is not None:
                        self.scraper.saveToDB(flist, self.db)

                    # Replace with config values
                    time.sleep(0.1)

            except LongPollReload as m:
                tsprint('Longpoll Reload: '.format(m))
                self.scraper.resetSession()
                continue

    def run(self):
        try:
            self.mainLoop()
        except KeyboardInterrupt:
            tsprint('User Quit.')
            sys.exit(0)
