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

@bp.route('/')
def index():
    db = get_db()
    posts = request_fetchall('SELECT p.id, title, body, created, author_id, username FROM preds p JOIN users u ON p.author_id = u.id ORDER BY created DESC', ['id', 'title', 'body', 'created', 'author_id', 'username'])
    last_pred_id = -1
    try :
        pred = request_fetchone("SELECT id FROM preds WHERE author_id = ? ORDER BY created DESC", ['id'], (g.user['id'],))
        last_pred_id = pred['id']
    except:
        print("DIDNT WORK")
        pass
    fig = None
    graphJSON = None
    fig = create_plot(last_pred_id)
    graphJSON=json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    boss = None
    last_post_id = -1
    if g.user :
        boss = (g.user['username']=="auglambert" or g.user['username']=='martinfeys')
        last_post_id = get_last_pred_id(g.user['id'])
    return render_template('blog/index.html', posts=posts, graphJSON = graphJSON, lenght = [i for i in range(len(posts))], boss= boss, editable_id=last_post_id)


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
    last_date = real_hospi.iloc[-1]['DATE']
    last_date = datetime.datetime.strptime(last_date, date_format)
    last_date = min(last_date, datetime.datetime.strptime(datetime.datetime.strftime(x[-1], date_format), date_format))
    last_date = datetime.datetime.strftime(last_date, date_format)
    y_real = real_hospi.loc[real_hospi['DATE']>=str(x[0])]
    y_real = y_real.loc[y_real['DATE'] <= last_date]['NEW_IN']
    y_real = list(y_real)
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


@bp.route('/create', methods=('GET', 'POST'))
def create():
    return redirect(url_for('blog.index'))

def get_post(id, check_author=True):
    post = request_fetchone('SELECT p.id, title, body, created, author_id, username'
        ' FROM preds p JOIN users u ON p.author_id = u.id'
        ' WHERE p.id = ?',
        ['id', 'title', 'body', 'created', 'author_id', 'username'],
        (id,))

    if check_author and post['author_id'] != g.user['id']:
        abort(403)

    return post


def get_pred(author_id, check_author=False):
    post = request_fetchone('SELECT username, pred1, pred2, pred3, pred4, pred5, pred6, pred7, pred8, pred9, pred10, pred11, pred12, pred13, pred14, pred15, pred16, pred17, pred18, pred19, pred20, pred21, pred22, pred23, pred24, pred25, pred26, pred27, pred28, pred29, pred30 FROM preds p JOIN users u ON p.author_id = u.id WHERE p.author_id = ? ORDER BY created DESC',
        ['username', 'pred1', 'pred2', 'pred3', 'pred4', 'pred5', 'pred6', 'pred7', 'pred8', 'pred9', 'pred10', 'pred11', 'pred12', 'pred13', 'pred14', 'pred15', 'pred16', 'pred17', 'pred18', 'pred19', 'pred20', 'pred21', 'pred22', 'pred23', 'pred24', 'pred25', 'pred26', 'pred27', 'pred28', 'pred29', 'pred30'],
        (author_id,))

    if check_author and post['author_id'] != g.user['id']:
        abort(403)

    return post

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

def get_ids():
    author_id = request_fetchall("Select DISTINCT author_id From preds", ['author_id'])

    if author_id is None : 
        abort(404, f"No one submitted a prediction.")
    return author_id

@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    post = get_post(id)

    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']
        error = None

        if not title:
            title = request_fetchone("SELECT title FROM preds WHERE id = ?", ['title'] ,(id))

        if error is not None:
            flash(error)
        else:
            insert_or_update('UPDATE preds SET title = ?, body = ?'
                ' WHERE id = ?',
                (title, body, id))
            
            return redirect(url_for('blog.index'))

    return render_template('blog/update.html', post=post)

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    post = get_post(id)
    if post['author_id'] == g.user['id']:
        insert_or_update('DELETE FROM preds WHERE id = ?', (id,))
    return redirect(url_for('blog.index'))

@bp.route('/dldb', methods=('GET', 'POST'))
@login_required
def dldb():
    path = "../database/flaskr.sqlite"
    if g.user['username']=='auglambert' or g.user['username']=='martinfeys':
        delete_all_non_mondays()
    return redirect(url_for('blog.index'))