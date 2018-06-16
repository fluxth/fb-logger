import collections
import codecs
import json

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

def timestamp(format='%Y-%m-%d %H:%M:%S'):
    return datetime.now().strftime(format)

def tsprint(pl, *args, **kwargs):
    ts = timestamp()
    print('[{}] {}'.format(ts, pl), *args, **kwargs)

def dprint(pl, *args, **kwargs):
    # Check if debug is enabled
    if True:
        print('* {}'.format(pl), *args, **kwargs)