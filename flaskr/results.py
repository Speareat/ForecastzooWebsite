from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, Response, send_file
)
from requests.api import get
from werkzeug.exceptions import abort

from flaskr.auth import login_required
from flaskr.db import get_db, request_fetchall

import pandas as pd
import plotly
import plotly.express as px
import json
from .blog import create_plot
from .predictions import get_mean_hospi

import numpy as np
from sklearn.metrics import mean_squared_error
import io
import datetime
import requests
import os

bp = Blueprint('results', __name__, url_prefix='/results')

@bp.route('/', methods=('GET', 'POST'))
def dashboard():
    return render_template('results/dashboard.html', duration="Choose the contest duration !")

@bp.route('/week<int:week>')
def get_week(week):
    items = []
    predicts = get_preds()

    #create reality
    real_hospi = get_mean_hospi().iloc[-week*7:]

    for idx, row in enumerate(predicts):

        x = np.zeros(30)
        for i in range(30):
            x[i]=row['pred'+str(i+1)]
        score = get_score(row['created'], x, real_hospi)

        an_item = dict(date=row["created"], username=row["username"], score=score, id=row['id'])
        items.append(an_item)
    items.sort(key=lambda item: item.get("score"))
    for i, item in enumerate(items) : 
        item['ranking']=i+1

    duration = "" 
    if week==1 : duration = 'Contest result for the past week'
    if week==2 : duration = 'Contest result for the past 2 weeks'
    if week==3 : duration = 'Contest result for the past 3 weeks'
    if week==4 : duration = 'Contest result for the past month'
    return render_template('results/dashboard.html', week=week, items=items, duration = duration)


def get_preds():
    post = request_fetchall('SELECT U.username, P.id, P.created, P.pred1, P.pred2, P.pred3, P.pred4, P.pred5, P.pred6, P.pred7, P.pred8, P.pred9, P.pred10, P.pred11, P.pred12, P.pred13, P.pred14, P.pred15, P.pred16, P.pred17, P.pred18, P.pred19, P.pred20, P.pred21, P.pred22, P.pred23, P.pred24, P.pred25, P.pred26, P.pred27, P.pred28, P.pred29, P.pred30 from preds P, users U where U.id=P.author_id',
    ['username', 'id', 'created', 'pred1', 'pred2', 'pred3', 'pred4', 'pred5', 'pred6', 'pred7', 'pred8', 'pred9', 'pred10', 'pred11', 'pred12', 'pred13', 'pred14', 'pred15', 'pred16', 'pred17', 'pred18', 'pred19', 'pred20', 'pred21', 'pred22', 'pred23', 'pred24', 'pred25', 'pred26', 'pred27', 'pred28', 'pred29', 'pred30'])
    
    if post is None:
        abort(404, f"No predictions in the database")
    return post 

def get_score(created, pred, real_hospi):
    str_created = created.strftime("%Y-%m-%d")
    real_hosp = real_hospi[real_hospi.DATE>=str_created]
    reals = list(real_hosp['NEW_IN'])
    preds = pred[:len(reals)]
    if not len(reals) or not len(preds):
        return 2147483647
    return mean_squared_error(reals, preds)

