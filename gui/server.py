from flask import Flask, request, session, redirect, render_template, make_response

from ..fblogger.Utils import load_config, timeago, format_datetime
from ..fblogger.Database import LogDatabase

import msgpack
import json

import math
from datetime import datetime

app = Flask(__name__)

config = load_config('./config.json')
db = LogDatabase(config['database'], check_same_thread=False)

app.secret_key = config['secrets']['flask']

app.jinja_env.filters['timeago'] = timeago 
app.jinja_env.filters['dt'] = format_datetime 

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


