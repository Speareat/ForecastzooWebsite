from datetime import datetime
import sqlite3

import os
import psycopg2

import click
from flask import current_app, g
from flask.cli import with_appcontext

def get_db():
    if 'db' not in g:
        if 'DATABASE_URL' in os.environ:
            g.heroku = True
        else:
            g.heroku = False
        if g.heroku:
            print('heroku')
            DATABASE_URL = os.environ['DATABASE_URL']
            g.connection = psycopg2.connect(DATABASE_URL, sslmode='require')
            g.db = g.connection.cursor()
            try:
                _ = g.db.execute('SELECT * FROM preds')
                _ = g.db.fetchone()
            except:
                g.connection.rollback()
                g.db = g.connection.cursor()
                begin = current_app.open_resource('droppostgresql.sql', 'r').read()
                g.db.execute(begin)
                next = current_app.open_resource('schemapostgresql.sql', 'r').read()
                g.db.execute(next)
        else:
            print('local')
            g.db = sqlite3.connect(
                current_app.config['DATABASE'],
                detect_types=sqlite3.PARSE_DECLTYPES
            )
            g.db.row_factory = sqlite3.Row
            try:
                _ = g.db.execute('SELECT * FROM preds').fetchall()
            except:
                with current_app.open_resource('schema.sql') as f:
                    g.db.executescript(f.read().decode('utf8'))

    return g.db

def transform_to_postgresql(request):
    new_request = ''
    for character in request:
        if character=='?':
            new_request += '%s'
        else:
            new_request += character
    return new_request

def insert_or_update(request, values=None):
    db = get_db()
    if g.heroku:
        request = transform_to_postgresql(request)
        if values is None:
            db.execute(request)
        else:
            db.execute(request, values)
        g.connection.commit()
    else:
        if values is None:
            db.execute(request).fetchone()
        else:
            db.execute(request, values).fetchone()
        db.commit()

def data_to_dico(keys, data):
    if data is None:
        return None
    dico = {}
    for i in range(len(keys)):
        dico[keys[i]]=data[i]
    return dico

def request_fetchone(request, keys, values=None):
    db = get_db()
    if g.heroku:
        request = transform_to_postgresql(request)
        if values is None:
            db.execute(request)
            data = db.fetchone()
        else:
            db.execute(request, values)
            data = db.fetchone()
        return data_to_dico(keys, data)
    else:
        if values is None:
            return db.execute(request).fetchone()
        else:
            return db.execute(request, values).fetchone()

def request_fetchall(request, keys, values=None):
    db = get_db()
    if g.heroku:
        request = transform_to_postgresql(request)
        if values is None:
            db.execute(request)
            datas = db.fetchall()
        else:
            db.execute(request, values)
            datas = db.fetchall()
        final = []
        for data in datas:
            final.append(data_to_dico(keys, data))
        return final
    else:
        if values is None:
            return db.execute(request).fetchall()
        else:
            return db.execute(request, values).fetchall()

def auto_keys(table):
    if table == 'parameters':
        return ['name', 'value']
    if table == 'users':
        return ['id', 'username', 'email', 'password']
    if table == 'preds':
        return ['id', 'author_id', 'created', 'title', 'body', 'pred1', 'pred2', 'pred3', 'pred4', 'pred5', 'pred6', 'pred7', 'pred8', 'pred9', 'pred10', 'pred11', 'pred12', 'pred13', 'pred14', 'pred15', 'pred16', 'pred17', 'pred18', 'pred19', 'pred20', 'pred21', 'pred22', 'pred23', 'pred24', 'pred25', 'pred26', 'pred27', 'pred28', 'pred29', 'pred30']
    if table == 'post':
        return ['id', 'author_id', 'created', 'title', 'body']


def delete_all_non_mondays():
    all_preds = request_fetchall('SELECT * FROM preds', auto_keys('preds'))
    date_format = "%Y-%m-%d"
    for pred in all_preds:
        if pred['created'].weekday() != 0:
            if pred['author_id'] == g.user['id']:
                insert_or_update('DELETE FROM preds WHERE id = ?', (pred['id'],))

def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

def init_db():
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing db and create new tables"""
    init_db()
    click.echo('Initialized the db.')


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
