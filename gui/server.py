from flask import Flask, request, session, redirect, render_template, make_response

from ..fblogger.Utils import load_config
from ..fblogger.Database import LogDatabase

import msgpack
import json

import math
from datetime import datetime

app = Flask(__name__)

config = load_config('./config.json')
db = LogDatabase(config['database'], check_same_thread=False)

app.secret_key = config['secrets']['flask']

def timeago(time):
    now = datetime.now()
    if type(time) is int:
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time,datetime):
        diff = now - time
    elif not time:
        diff = now - now

    second_diff = int(diff.seconds)
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return ""
        if second_diff < 60:
            return str(second_diff) + "s"
        if second_diff < 120:
            return "1m"
        if second_diff < 3600:
            return str(math.floor(second_diff / 60)) + "m"
        if second_diff < 7200:
            return "h"
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

    # diff = int(time.time()) - value
    # return '{}s'.format(diff)

app.jinja_env.filters['timeago'] = timeago 

@app.route('/')
def root():
    # If not logged in:
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == 'sani':
            session['username'] = 'sani'
            return redirect('/users')

    return render_template('login.html')

@app.route('/logout', methods=['GET'])
def logout():
    # REAL USER MANAGEMENT LATER!
    session.pop('username')
    return redirect('/login')

@app.route('/users')
def users():
    if session.get('username', None) is not None:
        return render_template('users.html', users=db.listUsers())
    else:
        return redirect('/login')

@app.route('/api')
def api_root():
    return redirect('/')
    # code 0    = success
    # code 1x   = request error
    # code 2x   = auth error

def msgpack_resp(payload):
    data = msgpack.packb(payload)
    resp = make_response(data)
    resp.headers.set('Content-Type', 'application/octet-stream')
    return resp


