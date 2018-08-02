from flask import Flask, request, session, redirect, render_template, make_response, send_from_directory

from fblogger.Utils import load_config, timeago, format_datetime
from fblogger.Database import LogDatabase, LogType

import msgpack
import json

import math
from datetime import datetime, time, timedelta

app = Flask(__name__)

config = load_config('./config.json')
db = LogDatabase(config['database'], check_same_thread=False)

app.secret_key = config['secrets']['flask']

def logtype2text(logtype):
    return LogType(logtype).name

def quotejson(inp):
    return json.dumps(inp, separators=(',', ':')).replace('null', '_').replace('"', '\\"')

app.jinja_env.filters['timeago'] = timeago 
app.jinja_env.filters['dt'] = format_datetime 
app.jinja_env.filters['logtype2text'] = logtype2text
app.jinja_env.filters['quotejson'] = quotejson

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

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

def get_timeline_plot(uid, start_ts):
    data = db.getTimelinePlotData(uid, start_ts)
    last = None
    for k, i in enumerate(data):
        if i[1] is None and i[2] == LogType.CHATPROXY_LONGPOLL.value and last is not None:
            data[k][1] = last

        if i[1] is not None:
            last = i[1]

        del data[k][2]

    return data

@app.route('/user/<int:user_id>')
def user_detail(user_id):
    if session.get('username', None) is not None:
        midnight = datetime.combine(datetime.today(), time.min)
        yesterday_midnight = midnight - timedelta(days=1)
        return render_template(
            'user_detail.html', 
            user=db.getUser(user_id), 
            logs=db.getUserActivities(user_id),
            timeline=[
                get_timeline_plot(user_id, midnight.timestamp()),
                get_timeline_plot(user_id, yesterday_midnight.timestamp()),
            ],
            timeline_now=(datetime.now().timestamp() - midnight.timestamp()) / 86400,
        )
    else:
        return redirect('/login')

@app.route('/api')
def api_root():
    return redirect('/')
    # code 0    = success
    # code 1x   = request error
    # code 2x   = auth error

@app.route('/api/user/<int:user_id>', methods=['POST'])
def api_user_details(user_id):
    if request.form.get('type', None) == 'timeline':
        seq = int(request.form.get('seq', 0))
        midnight = datetime.combine(datetime.today(), time.min)
        target_midnight = midnight - timedelta(days=seq-1)
        return json_resp({
            'code': 0,
            'seq': seq,
            'header': target_midnight.strftime('%a, %b %-d, %Y'),
            'payload': quotejson(get_timeline_plot(
                user_id, 
                target_midnight.timestamp()
            ))
        })

    return json_resp({
        'code': 10,
        'msg': 'Invalid Request',
    })

def msgpack_resp(payload):
    data = msgpack.packb(payload)
    resp = make_response(data)
    resp.headers.set('Content-Type', 'application/octet-stream')
    return resp

def json_resp(payload):
    data = json.dumps(payload)
    resp = make_response(data)
    resp.headers.set('Content-Type', 'application/json')
    return resp


