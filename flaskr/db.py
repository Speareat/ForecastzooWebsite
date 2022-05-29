from datetime import datetime
import sqlite3

import os
import psycopg2

import click
from flask import current_app, g
from flask.cli import with_appcontext

# Connect to the database, no matter if the website is on heroku or local, and checks if the database is clean
# and store on g.heroku if the connection is on heroku or local
def get_db():
    if 'db' not in g:
        if 'DATABASE_URL' in os.environ:
            g.heroku = True
        else:
            g.heroku = False
        if g.heroku:
            DATABASE_URL = os.environ['DATABASE_URL']
            g.connection = psycopg2.connect(DATABASE_URL, sslmode='require')
            g.db = g.connection.cursor()
            is_heroku_db_clean()
        else:
            g.db = sqlite3.connect(
                current_app.config['DATABASE'],
                detect_types=sqlite3.PARSE_DECLTYPES
            )
            g.db.row_factory = sqlite3.Row
            is_local_db_clean()

    return g.db

# Check if the database is clean, if not, drop the tables and create them again from scratch
def is_heroku_db_clean():
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
    try:
        _ = g.db.execute('SELECT * FROM means')
        _ = g.db.fetchone()
    except:
        g.connection.rollback()
        refresh_means()

# Check if the database is clean, if not, drop the tables and create them again from scratch
def is_local_db_clean():
    try:
        _ = g.db.execute('SELECT * FROM preds').fetchall()
    except:
        with current_app.open_resource('schema.sql') as f:
            g.db.executescript(f.read().decode('utf8'))
    try:
        _ = g.db.execute('SELECT * FROM means').fetchall()
    except:
        refresh_means()

# Drop and create the mean table
def refresh_means():
    if g.heroku:
        g.db = g.connection.cursor()
        g.db.execute(current_app.open_resource('means_table.sql', 'r').read())
    else:
        with current_app.open_resource('means_table.sql') as f:
            g.db.executescript(f.read().decode('utf8'))

# Tranform the request to the postgresql format
def transform_to_postgresql(request):
    new_request = ''
    for character in request:
        if character=='?':
            new_request += '%s'
        else:
            new_request += character
    return new_request

# Apply the queries that changes the database (only insert, update, deletes)
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

# Convert the postgresql request results to a dico (as the result of a sqlite request)
def data_to_dico(keys, data):
    if data is None:
        return None
    dico = {}
    for i in range(len(keys)):
        dico[keys[i]]=data[i]
    return dico

# Apply the fetchone requests to the database (heroku or local)
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

# Apply the fetchall requests to the database (heroku or local)
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

# Returns the keys of the asked table
def auto_keys(table):
    if table == 'parameters':
        return ['name', 'value']
    if table == 'users':
        return ['id', 'username', 'email', 'password']
    if table == 'preds':
        return ['id', 'author_id', 'created', 'title', 'body', 'pred1', 'pred2', 'pred3', 'pred4', 'pred5', 'pred6', 'pred7', 'pred8', 'pred9', 'pred10', 'pred11', 'pred12', 'pred13', 'pred14', 'pred15', 'pred16', 'pred17', 'pred18', 'pred19', 'pred20', 'pred21', 'pred22', 'pred23', 'pred24', 'pred25', 'pred26', 'pred27', 'pred28', 'pred29', 'pred30']
    if table == 'post':
        return ['id', 'author_id', 'created', 'title', 'body']
    if table == 'means':
        return ['date', 'value']

# Delete all predictions made another day than Monday
def delete_all_non_mondays():
    all_preds = request_fetchall('SELECT * FROM preds', auto_keys('preds'))
    date_format = "%Y-%m-%d"
    for pred in all_preds:
        if pred['created'].weekday() != 0:
            if pred['author_id'] == g.user['id']:
                insert_or_update('DELETE FROM preds WHERE id = ?', (pred['id'],))

# Close the database connection
def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

# Initialize the database
def init_db():
    db = get_db()

    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))

# Allow the command init-db
@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing db and create new tables"""
    init_db()
    click.echo('Initialized the db.')


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
