# Facebook Online-status Logger
Quite a little privacy red-pill.

## Installation
First, clone this repository to your server/computer:
```
$ git clone https://github.com/fluxTH/fb-logger.git
```

Next, install the required dependencies using `pip`:
```
$ pip3 install -r requirements.txt
```

Now, create your `config.json` file from the example provided:
```
$ cd fb-logger/
$ cp config.json.example config.json
```

Edit your config file with your Facebook credentials in the `credentials` section.
- `cuser` refers to your Facebook numeric ID
- `xs` refers to your Facebook `xs` cookie value
  - **Warning:** Take note of your cookie expiration date, as you'll need to update your `xs` with new value when it expires.

## Usage
`fb-logger` is designed to run as a long-running process, currently `daemon` mode is not supported, yet.

This program saves all your acquired data to `fblog.db` file.

To start your logger, run:
```
$ python3 fblogger.py
```

When you want your logger to run even when the terminal window is closed, use:
```
$ python3 fblogger.py > /dev/null &
```
Notice that this command won't output anything to `STDOUT`, this is where the `fblogger.log` file comes in.

To stop the logger, use `CTRL + C` in normal mode.
In long-running mode, use:
```
$ kill -9 $(cat fblogger.pid)
```

## Config

All the configuration options available in `config.json`, refer to `config.json.example` for default values.

### General Configuration
| Key 						| Type 		| Description 	|
| --- 						| --- 		| --- 			|
| `debug` 					| Boolean	| (Not Implemented) Enable debugging functionalities. |
| `database` 				| String	| **_Required._** Path to database file. |
| `pid_file` 				| String	| Path to file containing PID. |
| `log_file` 				| String	| Path to runtime log file. |

### Credential Configuration
| Key 						| Type 		| Description 	|
| --- 						| --- 		| --- 			|
| `credentials.c_user` 		| String 	| **_Required._** Facebook numeric ID. |
| `credentials.xs` 			| String	| **_Required._** Value of `xs` cookie on Facebook web. |

### Secret Key Configuration
| Key 						| Type 		| Description 	|
| --- 						| --- 		| --- 			|
| `secrets.brunca` 			| String 	| (Not Implemented) Secret encryption key for brunca tokens. (32 bytes) |
| `secrets.flask` 			| String	| **_Required._** Web GUI secret encryption key. |

### Scraper Configuration
| Key 						| Type 		| Description 	|
| --- 						| --- 		| --- 			|
| `scraper.cache_lb` 		| Boolean	| |
| `scraper.sticky_expire` 	| Integer	| Seconds to invalidate sticky cookie cache. |
| `scraper.longpoll`	 	| Boolean	| (Not Implemented) Enables longpolling. |
| `scraper.longpoll_timeout`| Boolean	| (Not Implemented) Seconds to wait for a longpoll request. |
| `scraper.poll_interval` 	| Integer	| Seconds to wait until new full request. (Not used if in longpoll mode) |
| `scraper.request_timeout`	| Integer	| Seconds to wait for a full request. |
| `scraper.retry_timeout` 	| Integer	| Seconds to wait before trying again in case of error. |
| `scraper.retry_limit` 	| Integer	| Limit of failed retry attempts. |
| `scraper.chill_timeout` 	| Integer	| Seconds to wait if retry attempt reached limit. |
