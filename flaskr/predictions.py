import datetime
from os import error
from sqlite3.dbapi2 import DateFromTicks
from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, Response, make_response, send_file, current_app
)
from werkzeug.exceptions import abort

from flaskr.auth import login_required
from flaskr.db import auto_keys, get_db, insert_or_update, refresh_means, request_fetchone, request_fetchall

import pandas as pd
import numpy as np
import requests
from io import StringIO
import plotly
import plotly.express as px
import json
import os
import matplotlib.pyplot as plt
import shutil

bp = Blueprint('predictions', __name__, url_prefix='/predictions')

# Handle the choice of the prediction model
@bp.route('/<string:changes>', methods=('GET', 'POST'))
def choice_of_pred_type(changes):
    if request.method == 'POST':
        method = request.form['method']
        if method=='manually':
            return redirect(url_for("predictions.manual_predictions", changes=changes))
        elif method=='csvfile':
            return redirect(url_for("predictions.csv_predictions", changes=changes))
        elif method=='draw':
            return redirect(url_for("predictions.draw_predictions", changes=changes))

    return render_template("predictions/choice_pred.html")

# Allow to see a prediction (id given as input)
@bp.route('/see/<int:id>', methods=('GET', 'POST'))
def see(id):
    post = request_fetchone('SELECT * FROM preds WHERE id = ?', auto_keys('preds'),(id,))
    fig = create_plot(id)
    graphJSON=json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return render_template("predictions/see_pred.html", post=post, graphJSON = graphJSON)

# Allow to download a prediction (id given as input)
@bp.route('/downloads/<int:id>', methods=('GET', 'POST'))
def downloads(id):
    pred = get_pred_modif(id)
    x = np.zeros(30)
    for i in range(30):
        x[i]=pred['pred'+str(i+1)]
    df = pd.DataFrame(x, index=None, columns=None)
    resp = make_response(df.to_csv(index=False, header=False))
    resp.headers["Content-Disposition"] = "attachment; filename=export.csv"
    resp.headers["Content-Type"] = "text/csv"
    return resp

# Handle the drawn prediction
@bp.route('/<string:changes>draw', methods=('GET', 'POST'))
def draw_predictions(changes):
    if request.method =='POST':
        error = None
        title = request.form['title']
        body = request.form['body']
        drawn = request.form['getDrawn']
        drawn = drawn.split(',')

        #ONLY used if g.edit
        change_title = True
        change_body = True

        if title == "":
            change_title = False
            title = 'Predictions of '+str(g.user['username'])+' ('+str(datetime.date.today())+')'
        
        if body == "":
            change_body = False

        # [canvas.clientLeft, canvas.clientTop, canvas.clientWidth, canvas.clientHeight]
        data_window = request.form['data_window']
        # Case when the user draw a new prediction (or redraw to edit)
        if g.edit is None or len(drawn)>1:
            data_window = data_window.split(',')
            for i in range(len(data_window)):
                data_window[i]=int(data_window[i])
            
            points_drawn = []
            x_drawn = []
            y_drawn = []
            # Unpack each drawn point
            for i in range(0, len(drawn), 2):
                points_drawn.append((int(drawn[i]), int(drawn[i+1])))
                x_drawn.append(int(drawn[i]))
                y_drawn.append(int(drawn[i+1]))
            
            # Pixel values to know the proportion of the canvas and compute the real values predicted
            valeurs_image_w = [0, 159, 576, 640]
            valeurs_image_h = [0, 59, 427, 480]

            deformation_max_x = (data_window[2]/valeurs_image_w[3])
            deformation_max_y = (data_window[3]/valeurs_image_h[3])

            if deformation_max_x > deformation_max_y:
                def_max = deformation_max_y
            else:
                def_max = deformation_max_x

            min_x = valeurs_image_w[1] * deformation_max_x
            max_x = valeurs_image_w[2] * deformation_max_x

            max_y = valeurs_image_h[1] * deformation_max_y
            min_y = valeurs_image_h[2] * deformation_max_y

            # get last date of the graph
            hospi_mean = get_mean_hospi()
            last_date_graph = hospi_mean.iloc[-1]['DATE']
            date_format = "%Y-%m-%d"
            days_before = (datetime.datetime.today() - datetime.datetime.strptime(last_date_graph, date_format)).days 

            gap = (max_x-min_x)/(30.0+days_before)
            max_gap = gap * 3
            y = []

            currX = min_x
            index = 0

            if g.monday is None:
                error = "Predictions are only allowed on mondays"

            # Compute the prediction for each day
            for i in range(30+days_before):
                while error is None and index<len(x_drawn)-1 and x_drawn[index] < currX:
                    index+=1
                if x_drawn[index] == currX:
                    if i > days_before-1:
                        y.append(y_drawn[index])
                else:
                    if index==0:
                        if x_drawn[index] > currX+gap:
                            error = "You must start next to the end of the previous curve."
                        elif i > days_before-1:
                            y.append(y_drawn[index])
                    elif index==len(x_drawn)-1:
                        if x_drawn[index] < currX-gap:
                            error = "You must end next to the right side of the box."
                        elif i > days_before-1:
                            y.append(y_drawn[index])
                    else:
                        point_gauche = x_drawn[index-1]
                        point_droite = x_drawn[index+1]
                        if point_droite-point_gauche > max_gap:
                            error = "You cannot let a gap bigger than 3 days."
                        elif i > days_before-1:
                            y_gauche = y_drawn[index-1]
                            y_droite = y_drawn[index+1]
                            ratio = (currX - point_gauche) / (point_droite-point_gauche)
                            y.append(y_gauche+(ratio*(y_droite-y_gauche)))
                currX += gap
            
            # For each day, compute the prediction based on the pixel on the canvas
            if error is None:
                min_hospi = 0
                f = open("flaskr\\static\\data\\maximax.txt", "r")
                line = f.readline()
                line = float(line)
                max_hospi = int(round(line))
                f.close()
                preds = []
                for point in y:
                    ecart = (point - max_y) / (min_y - max_y)
                    ratio = 1 - ecart
                    preds.append(max(0, int(ratio * (max_hospi - min_hospi) + min_hospi)))
            
                db = get_db()
                # If it is an edition, update the prediction
                if g.edit:
                    previous = request_fetchone("SELECT * FROM preds WHERE author_id = ? ORDER BY created DESC", auto_keys('preds'), (g.user['id'],))
                    # put data in db
                    if not change_title:
                        title = previous['title']
                    if not change_body:
                        body = previous['body']
                    values = [title, body]
                    size = len(preds)
                    for d in preds:
                        values.append(int(d))
                    requestString = 'UPDATE preds SET title = ?, body = ?'
                    for i in range(1, size+1):
                        requestString = requestString+', pred'+str(i)+' = ?'
                    requestString = requestString + 'WHERE id = ?'
                    values.append(previous['id'])
                    insert_or_update(requestString, tuple(values))
                    return redirect(url_for("blog.index"))
                # If it is a new prediction, insert it
                else:
                    values = [g.user['id'], title, body]
                    for i in range(len(preds)):
                        values.append(preds[i])
                    requestString = 'INSERT INTO preds (author_id, title, body'
                    appendString = '(?, ?, ?'
                    for i in range(1, len(preds)+1):
                        requestString = requestString+', pred'+str(i)
                        appendString = appendString+', ?'
                    requestString = requestString+') VALUES '+appendString+')'

                    insert_or_update(requestString, tuple(values))

                    return redirect(url_for('blog.index'))
                
            else:
                flash(error)
        else:
            # Case when the user already made a pred and simply edited the title or body
            db = get_db()
            previous = request_fetchone("SELECT * FROM preds WHERE author_id = ? ORDER BY created DESC", auto_keys('preds'), (g.user['id'],))
            if not change_title:
                title = previous['title']
            if not change_body:
                body = previous['body']
            values = [title, body, previous['id']]
            requestString = 'UPDATE preds SET title = ?, body = ? WHERE id = ?'
            insert_or_update(requestString, tuple(values))
            return redirect(url_for("blog.index"))

    create_draw_plot()
    return render_template("predictions/drawWithMouse_pred.html")

# Handle the csv prediction
@bp.route('/<string:changes>csvfile', methods=('GET', 'POST'))
def csv_predictions(changes):
    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']

        #ONLY used if g.edit
        change_title = True
        change_body = True
        error = None
        if g.monday is None:
                error = "Predictions are only allowed on mondays"

        # Load title, body and csv file
        if title == "":
            change_title = False
            title = 'Predictions of '+str(g.user['username'])+' ('+str(datetime.date.today())+')'
        
        if body == "":
            change_body = False

        files = request.files['file']
        
        data = None
        # Read the csv file
        try:  
            data = pd.read_csv(files, header=None).to_numpy()
        except:
            flash('Impossible to read file.')
            return render_template("predictions/csv_pred.html")
        
        db = get_db()

        if error is None:
            # If it is an edition, update the prediction
            if changes!="new":
                previous = request_fetchone("SELECT * FROM preds WHERE author_id = ? ORDER BY created DESC", auto_keys('preds'), (g.user['id'],))
                # put data in db
                if not change_title:
                    title = previous['title']
                if not change_body:
                    body = previous['body']
                values = [title, body]
                size = len(data)
                for d in data:
                    values.append(int(d))
                requestString = 'UPDATE preds SET title = ?, body = ?'
                for i in range(1, size+1):
                    requestString = requestString+', pred'+str(i)+' = ?'
                requestString = requestString + 'WHERE id = ?'
                values.append(previous['id'])
                insert_or_update(requestString, tuple(values))
                return redirect(url_for("blog.index"))

            # If it is a new prediction, insert it
            else:
                # put data in db
                values = [g.user['id'], title, body]
                size = len(data)
                for d in data:
                    values.append(int(d))
                requestString = 'INSERT INTO preds (author_id, title, body'
                appendString = '(?, ?, ?'
                for i in range(1, size+1):
                    requestString = requestString+', pred'+str(i)
                    appendString = appendString+', ?'
                requestString = requestString+') VALUES '+appendString+')'

                insert_or_update(requestString, tuple(values))


                return redirect(url_for("blog.index"))
        else:
            flash(error)
        
    if changes=='edit':
        pred = get_pred_modif(str(g.user['id']))
        return render_template("predictions/csv_pred.html", pred = pred)
    else : 
        pred = None
        return render_template("predictions/csv_pred.html", pred = pred)

# Handle the manual prediction
@bp.route('/<string:changes>manual', methods=('GET', 'POST'))
def manual_predictions(changes):
    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']

        #ONLY used if g.edit
        change_title = True
        change_body = True
        
        # Load title and body
        if title == "":
            change_title = False
            title = 'Predictions of '+str(g.user['username'])+' ('+str(datetime.date.today())+')'
        
        if body == "":
            change_body = False
        
        error = None
        if g.monday is None:
                error = "Predictions are only allowed on mondays"

        db = get_db()
        if error is None:
            # If it is an edition, update the prediction
            if g.edit:
                previous = request_fetchone("SELECT * FROM preds WHERE author_id = ? ORDER BY created DESC", auto_keys('preds'), (g.user['id'],))
                # put data in db
                if not change_title:
                    title = previous['title']
                if not change_body:
                    body = previous['body']
                values = [title, body]
                size = len(request.form)-2
                # Load all the values of the prediction
                for i in range(1, size+1):
                    values.append(request.form['pred'+str(i)])

                requestString = 'UPDATE preds SET title = ?, body = ?'
                for i in range(1, size+1):
                    requestString = requestString+', pred'+str(i)+' = ?'
                requestString = requestString + 'WHERE id = ?'
                values.append(previous['id'])
                insert_or_update(requestString, tuple(values))
                
                return redirect(url_for("blog.index"))
            # If it is a new prediction, insert it
            else:
                values = [g.user['id'], title, body]
                size = len(request.form)-2
                # Load all the values of the prediction
                for i in range(1, size+1):
                    values.append(request.form['pred'+str(i)])
                requestString = 'INSERT INTO preds (author_id, title, body'
                appendString = '(?, ?, ?'
                for i in range(1, size+1):
                    requestString = requestString+', pred'+str(i)
                    appendString = appendString+', ?'
                requestString = requestString+') VALUES '+appendString+')'

                insert_or_update(requestString, tuple(values))

                return redirect(url_for("blog.index"))
        else:
            flash(error)

    if changes=='edit':
        pred = get_pred_modif(str(g.user['id']))
        return render_template("predictions/manual_pred.html", pred = pred, val=[str(i) for i in range(1, 31)])
    else : 
        pred = None; val = None
        return render_template("predictions/manual_pred.html", pred = pred, val=val)

# Load the prediction to edit (from the author id)
def get_pred_modif(author_id, check_author=False):
    post = request_fetchone('SELECT title, body, pred1, pred2, pred3, pred4, pred5, pred6, pred7, pred8, pred9, pred10, pred11, pred12, pred13, pred14, pred15, pred16, pred17, pred18, pred19, pred20, pred21, pred22, pred23, pred24, pred25, pred26, pred27, pred28, pred29, pred30 from preds where author_id = ? order by created desc', 
    ['title', 'body', 'pred1', 'pred2', 'pred3', 'pred4', 'pred5', 'pred6', 'pred7', 'pred8', 'pred9', 'pred10', 'pred11', 'pred12', 'pred13', 'pred14', 'pred15', 'pred16', 'pred17', 'pred18', 'pred19', 'pred20', 'pred21', 'pred22', 'pred23', 'pred24', 'pred25', 'pred26', 'pred27', 'pred28', 'pred29', 'pred30'],
    (str(author_id)))

    if post is None:
        abort(404, f"Post id {id} doesn't exist.")

    if check_author and post['author_id'] != g.user['id']:
        abort(403)

    return post 


# HELPERS

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


# cree le plotly express line avec les vraies donnees precedant la pred pour dessiner dessus
def create_draw_plot(days_before=7):
    real_hospi = get_mean_hospi()
    y_real = real_hospi.iloc[-7:]
    date_format = "%Y-%m-%d"
    first_date = datetime.datetime.strptime(y_real['DATE'].tolist()[0], date_format)
    today = datetime.date.today().strftime(date_format)
    a = datetime.datetime.strptime(today, date_format)
    b = datetime.datetime.strptime(y_real['DATE'].tolist()[-1], date_format)
    delta_dates = (a-b).days
    nb_values = len(y_real)
    x = [(first_date+datetime.timedelta(i)).strftime(date_format) for i in range(30+len(y_real)+delta_dates)]
    dates = x[len(y_real):]
    df2 = pd.DataFrame({'DATE': dates, 'NEW_IN': [None for i in range(len(dates))]})
    y_real = y_real.append(df2)

    x = y_real['DATE'].tolist()
    for i in range(len(x)):
        tab = x[i].split('-')
        x[i] = tab[2]+'-'+tab[1]
    y = y_real['NEW_IN'].tolist()
    plt.plot(x, y)
    plt.xticks(ticks=[x[i] for i in range(0,len(x), 5)])
    plt.ylim((0, 3*np.max(y[:nb_values])))

    plt.savefig("flaskr\\data\\background.png")
    # Thanks to that line the update of the background graph is automaticly done
    shutil.move("flaskr\\data\\background.png", "flaskr\\static\\data\\background.png")
    with open("flaskr\\static\\data\\maximax.txt", "w") as f:
        f.write(str(3*np.max(y[:nb_values])))

    #plt.show()

# Handle the centered rolling average of the hospital admissions
def get_mean_hospi():
    db = get_db()
    path = 'data/Hospi_numbers/'
    name_basefile = 'sciensano_hosp.csv'
    filename = path+name_basefile 
    update_hosp_mean = request_fetchone('SELECT * FROM parameters WHERE name = ?', auto_keys('parameters'), ('hospi_mean_file',))
    mean_in_db = request_fetchall('SELECT * FROM means', auto_keys('means'))
    #mean_in_db = []
    # if the centered rolling average of the hospital admissions is not completely computed, compute it and then return it
    if update_hosp_mean is None or update_hosp_mean['value'] != datetime.date.today().strftime('%Y-%m-%d') or mean_in_db==[]:
        # DL new data
        url = 'https://epistat.sciensano.be/Data/COVID19BE_HOSP.csv'
        r = requests.get(url, allow_redirects=True)
        open(filename, 'wb').write(r.content)
        # open data
        official_data = pd.read_csv(filename)
        # somme des new in au niveau belge chaque jour
        belgium_new_in = pd.DataFrame(columns=['DATE', 'NEW_IN'])
        dates = []
        for date in official_data['DATE']:
            if date not in dates:
                dates.append(date)
        for date in dates:
            that_day = official_data.loc[official_data['DATE'] == date]
            sum = 0
            for i in range(len(that_day)):
                line = that_day.iloc[i]
                sum += line['NEW_IN']
            belgium_new_in = belgium_new_in.append({'DATE':date, 'NEW_IN':sum}, ignore_index=True)
        # faire la moyenne centree sur 'days' jours
        belgium_mean = pd.DataFrame(columns=['DATE', 'NEW_IN'])
        days = 5
        act_tab = []
        act_sum = 0
        i = 0
        center = int(days/2)
        for _ in range(days):
            act_tab.append(belgium_new_in.iloc[i]['NEW_IN'])
            act_sum += act_tab[i]
            i += 1
        while i < len(belgium_new_in):
            row_center = belgium_new_in.iloc[center]
            belgium_mean = belgium_mean.append({'DATE':row_center['DATE'], 'NEW_IN':act_sum/days}, ignore_index=True)
            act_sum -= act_tab[0]
            act_tab.remove(act_tab[0])
            i += 1
            center += 1
            if i < len(belgium_new_in):
                act_tab.append(belgium_new_in.iloc[i]['NEW_IN'])
                act_sum += act_tab[-1]
        for idx, row in belgium_mean.iterrows():
            if idx > len(mean_in_db):
                x, y = row['DATE'], row['NEW_IN']
                insert_or_update('INSERT INTO means (date, value) VALUES (?, ?)', (x, y))
        if update_hosp_mean is None:
            insert_or_update('INSERT INTO parameters (name, value) VALUES (?, ?)', ('hospi_mean_file', datetime.date.today().strftime('%Y-%m-%d')))
        else:
            insert_or_update('UPDATE parameters SET value = ? WHERE name = ?', (datetime.date.today().strftime('%Y-%m-%d'), 'hospi_mean_file'))
        return belgium_mean
    # if the centered rolling average of the hospital admissions is already computed, return it
    belgium_mean = pd.DataFrame(columns=['DATE', 'NEW_IN'])
    for dico in mean_in_db:
        belgium_mean = belgium_mean.append({'DATE':dico['date'], 'NEW_IN':float(dico['value'])}, ignore_index=True)
    return belgium_mean
