# Logger
class ContinueLoop(Exception):
    pass


# Database
class DatabaseException(Exception):
    pass

class MigrationException(DatabaseException):
    pass


# Scraper
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
