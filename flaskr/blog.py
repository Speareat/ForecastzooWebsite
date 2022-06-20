from sqlite3.dbapi2 import DateFromTicks
from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, Response, send_file
)
from requests.api import get
from werkzeug.exceptions import abort

from flaskr.auth import login_required
from flaskr.db import auto_keys, get_db, insert_or_update, request_fetchall, request_fetchone, delete_all_non_mondays
from flaskr.predictions import get_mean_hospi

import pandas as pd
import plotly
import plotly.express as px
import json

import numpy as np
import io
import datetime
import requests
import os

bp = Blueprint('blog', __name__)

# This runs the main page of the website
@bp.route('/')
def index():
    db = get_db()
    # Loads all the posts from the database (descending order by date)
    posts = request_fetchall('SELECT p.id, title, body, created, author_id, username FROM preds p JOIN users u ON p.author_id = u.id ORDER BY created DESC', ['id', 'title', 'body', 'created', 'author_id', 'username'])
    last_pred_id = -1
    # Loads the last prediction of the current user (if any)
    try :
        pred = request_fetchone("SELECT id FROM preds WHERE author_id = ? ORDER BY created DESC", ['id'], (g.user['id'],))
        last_pred_id = pred['id']
    except:
        pass
    fig = None
    graphJSON = None
    # Creates the plotly graph of the main page
    fig = create_plot(last_pred_id)
    graphJSON=json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    boss = None
    # Last_post_id is the id of the last post of the current user, it is given to the front-end to display the "edit" button
    last_post_id = -1
    if g.user :
        last_post_id = get_last_pred_id(g.user['id'])
    return render_template('blog/index.html', posts=posts, graphJSON = graphJSON, lenght = [i for i in range(len(posts))], editable_id=last_post_id)


# cree le plotly express line avec une pred et les vraies donnees precedant la pred
def create_plot(pred_id, days_before=7): 
    if pred_id > 0 :
        db = get_db()
        pred = request_fetchone('SELECT * FROM preds WHERE id = ?', auto_keys('preds'), (pred_id,))
        author = request_fetchone('SELECT * FROM users WHERE id = ?', auto_keys('users'), (pred['author_id'],))
        x = [pred['created']+datetime.timedelta(days=-days_before)+datetime.timedelta(days=i) for i in range(30+days_before)]
    else : 
        x = [datetime.date.today()+datetime.timedelta(days=-(3+days_before))+datetime.timedelta(days=i) for i in range(30+days_before)]
    
    df = pd.DataFrame(x, columns=['Journées'])
    columns = []
    # set values for real numbers
    date_format = "%Y-%m-%d"
    column_name = 'Reality'
    columns.append(column_name)
    real_hospi = get_mean_hospi()
    # find last date (of pred or reality)
    last_date = real_hospi.iloc[-1]['DATE']
    last_date = datetime.datetime.strptime(last_date, date_format)
    last_date = min(last_date, datetime.datetime.strptime(datetime.datetime.strftime(x[-1], date_format), date_format))
    last_date = datetime.datetime.strftime(last_date, date_format)
    # takes hospi values after the first date of prediction and before the last date (of prediction or reality)
    y_real = real_hospi.loc[real_hospi['DATE']>=str(x[0])]
    y_real = y_real.loc[y_real['DATE'] <= last_date]['NEW_IN']
    y_real = list(y_real)
    if len(y_real ) < 3 :
        return create_plot(pred_id, days_before = days_before+1)
    max_real = max(y_real)
    y_real.extend([None for i in range(len(y_real), 30+days_before)])
    df.insert(1, column_name, y_real)
    max_y = max_real

    if pred_id > 0 :
        if g.heroku:
            pred = list(pred.values())
        # set values for prediction
        column_name = author['username']
        columns.append(column_name)
        y_pred = [None for i in range(days_before)]
        y_pred.extend(pred[5:])
        df.insert(1, column_name, y_pred)

        max_y= max(max_real, max(pred[5:]))

    fig = px.line(df, x=x, y=columns, range_y=[0, max_y*2])
    return fig


# Get post informations (+- preds informations without the values of the prediction) from the database with the given id
def get_post(id, check_author=True):
    post = request_fetchone('SELECT p.id, title, body, created, author_id, username'
        ' FROM preds p JOIN users u ON p.author_id = u.id'
        ' WHERE p.id = ?',
        ['id', 'title', 'body', 'created', 'author_id', 'username'],
        (id,))

    if check_author and post['author_id'] != g.user['id']:
        abort(403)

    return post

# Get the id of the last prediction of the user with the given id
def get_last_pred_id(author_id, check_author=False):
    keys = auto_keys('preds')
    keys.extend(auto_keys('users'))
    post = request_fetchone('SELECT * FROM preds p JOIN users u ON p.author_id = u.id WHERE p.author_id = ? ORDER BY created DESC',
        keys,
        (author_id,))

    if post is None:
        return None

    if check_author and post['author_id'] != g.user['id']:
        abort(403)

    return post['id']

# Get the ids of all users that made a prediction
def get_ids():
    author_id = request_fetchall("Select DISTINCT author_id From preds", ['author_id'])

    if author_id is None : 
        abort(404, f"No one submitted a prediction.")
    return author_id

# Either auglambert or martinfeys may delete all potential predictions that were made another day than monday
@bp.route('/dldb', methods=('GET', 'POST'))
@login_required
def dldb():
    path = "../database/flaskr.sqlite"
    if g.user['username']=='auglambert' or g.user['username']=='martinfeys':
        delete_all_non_mondays()
    return redirect(url_for('blog.index'))