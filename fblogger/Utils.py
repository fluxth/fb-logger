import collections
import codecs
import json
import logging
import sys
import math

from datetime import datetime

def dict_merge(d, u):
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            d[k] = dict_merge(d.get(k, {}), v)
        else:
            d[k] = v
    return d

def load_config(path):
    try:
        return json.load(codecs.open(path, 'r', 'utf-8'))
    except FileNotFoundError:
        print('Error: Config file not found, check if "config.json" file exists.')
        sys.exit(1)
    except json.JSONDecodeError as m:
        print('Error: Cannot parse config file, check your "config.json" for JSON errors.')
        print('[Details: {}]'.format(m))
        sys.exit(1)

def resolve_dict(parent_dict, dotted_str):
    if '.' in dotted_str:
        keys = dotted_str.split('.')
        data = parent_dict

        for k in keys:
            data = data[k]

        return data
    return parent_dict[dotted_str]

def timestamp(format='%Y-%m-%d %H:%M:%S'):
    return datetime.now().strftime(format)

def tsprint(pl, *args, **kwargs):
    ts = timestamp()
    # TODO: Make entire different func for info print
    logging.info(pl)

    print('[{}] {}'.format(ts, pl), *args, **kwargs)

def dprint(pl, *args, **kwargs):
    # Check if debug is enabled
    if True:
        logging.debug(pl)
        print('* {}'.format(pl), *args, **kwargs)

def parse_to_datetime(time):
    if isinstance(time, datetime):
        return time

    if type(time) is int:
        return datetime.fromtimestamp(time)

    try:
        return datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None

def format_datetime(time):
    dt = parse_to_datetime(time)
    if dt is None:
        return time

    return datetime.strftime(dt, '%a, %b %-d, %Y at %-I:%M:%S %p')

def timeago(time):
    now = datetime.now()

    if not time:
        diff = now - now

    diff = now - parse_to_datetime(time)
    if diff is None:
        return time

    second_diff = int(diff.seconds)
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return str(second_diff) + "s"
        if second_diff < 120:
            return "1m"
        if second_diff < 3600:
            return str(math.floor(second_diff / 60)) + "m"
        if second_diff < 7200:
            return "1h"
        if second_diff < 86400:
            return str(math.floor(second_diff / 3600)) + "h"
    if day_diff == 1:
        return "1d"
    if day_diff < 7:
        return str(day_diff) + "d"
    if day_diff < 31:
        return str(day_diff / 7) + "w"
    if day_diff < 365:
        return str(day_diff / 30) + "mo"
    return str(day_diff / 365) + " y"
