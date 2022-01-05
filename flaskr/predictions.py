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

bp = Blueprint('predictions', __name__, url_prefix='/predictions')


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


@bp.route('/see/<int:id>', methods=('GET', 'POST'))
def see(id):
    post = request_fetchone('SELECT * FROM preds WHERE id = ?', auto_keys('preds'),(id,))
    fig = create_plot(id)
    graphJSON=json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return render_template("predictions/see_pred.html", post=post, graphJSON = graphJSON)


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
    
@bp.route('/<string:changes>draw', methods=('GET', 'POST'))
def draw_predictions(changes):
    if request.method =='POST':
        error = None
        title = request.form['title']
        body = request.form['body']
        drawed = request.form['getDrawed']
        drawed = drawed.split(',')

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
        if g.edit is None or len(drawed)>1:
            data_window = data_window.split(',')
            for i in range(len(data_window)):
                data_window[i]=int(data_window[i])
            
            points_drawed = []
            x_drawed = []
            y_drawed = []
            for i in range(0, len(drawed), 2):
                points_drawed.append((int(drawed[i]), int(drawed[i+1])))
                x_drawed.append(int(drawed[i]))
                y_drawed.append(int(drawed[i+1]))
            
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

            for i in range(30+days_before):
                while error is None and index<len(x_drawed)-1 and x_drawed[index] < currX:
                    index+=1
                if x_drawed[index] == currX:
                    if i > days_before-1:
                        y.append(y_drawed[index])
                else:
                    if index==0:
                        if x_drawed[index] > currX+gap:
                            error = "You must start next to the end of the previous curve."
                        elif i > days_before-1:
                            y.append(y_drawed[index])
                    elif index==len(x_drawed)-1:
                        if x_drawed[index] < currX-gap:
                            error = "You must end next to the right side of the box."
                        elif i > days_before-1:
                            y.append(y_drawed[index])
                    else:
                        point_gauche = x_drawed[index-1]
                        point_droite = x_drawed[index+1]
                        if point_droite-point_gauche > max_gap:
                            error = "You cannot let a gap bigger than 3 days."
                        elif i > days_before-1:
                            y_gauche = y_drawed[index-1]
                            y_droite = y_drawed[index+1]
                            ratio = (currX - point_gauche) / (point_droite-point_gauche)
                            y.append(y_gauche+(ratio*(y_droite-y_gauche)))
                currX += gap
            
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
            db = get_db()
            previous = request_fetchone("SELECT * FROM preds WHERE author_id = ? ORDER BY created DESC", auto_keys('preds'), (g.user['id'],))
            # put data in db
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

        if title == "":
            change_title = False
            title = 'Predictions of '+str(g.user['username'])+' ('+str(datetime.date.today())+')'
        
        if body == "":
            change_body = False

        files = request.files['file']
        
        data = None
        try:  
            data = pd.read_csv(files, header=None).to_numpy()
        except:
            flash('Impossible to read file.')
            return render_template("predictions/csv_pred.html")
        
        

        db = get_db()

        if error is None:
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


@bp.route('/<string:changes>manual', methods=('GET', 'POST'))
def manual_predictions(changes):
    if request.method == 'POST':
        title = request.form['title']
        body = request.form['body']

        #ONLY used if g.edit
        change_title = True
        change_body = True

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
            if g.edit:
            #if changes != "new":
                previous = request_fetchone("SELECT * FROM preds WHERE author_id = ? ORDER BY created DESC", auto_keys('preds'), (g.user['id'],))
                # put data in db
                if not change_title:
                    title = previous['title']
                if not change_body:
                    body = previous['body']
                values = [title, body]
                size = len(request.form)-2
                for i in range(1, size+1):
                    values.append(request.form['pred'+str(i)])

                requestString = 'UPDATE preds SET title = ?, body = ?'
                for i in range(1, size+1):
                    requestString = requestString+', pred'+str(i)+' = ?'
                requestString = requestString + 'WHERE id = ?'
                values.append(previous['id'])
                insert_or_update(requestString, tuple(values))
                
                return redirect(url_for("blog.index"))
            else:
                values = [g.user['id'], title, body]
                size = len(request.form)-2
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
    db = get_db()
    pred = request_fetchone('SELECT * FROM preds WHERE id = ?', auto_keys('preds'), (pred_id,))
    author = request_fetchone('SELECT * FROM users WHERE id = ?', auto_keys('users'), (pred['author_id'],))
    x = [pred['created']+datetime.timedelta(days=-days_before)+datetime.timedelta(days=i) for i in range(30+days_before)]
    df = pd.DataFrame(x, columns=['Journées'])
    columns = []
    # set values for real numbers
    column_name = 'Reality'
    columns.append(column_name)
    real_hospi = get_mean_hospi()
    last_date = real_hospi.iloc[-1]['DATE']
    last_date = min(str(last_date), str(x[-1]))
    y_real = real_hospi.loc[real_hospi['DATE']>=str(x[0]+datetime.timedelta(days=-1))]
    y_real = y_real.loc[y_real['DATE'] <= last_date]['NEW_IN']
    y_real = list(y_real)
    max_real = max(y_real)
    y_real.extend([None for i in range(len(y_real), 30+days_before)])
    df.insert(1, column_name, y_real)

    # set values for prediction
    pred = list(pred.values())
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
    with open("flaskr\\static\\data\\maximax.txt", "w") as f:
        f.write(str(3*np.max(y[:nb_values])))

    #plt.show()


def get_mean_hospi():
    db = get_db()
    path = 'data/Hospi_numbers/'
    name_basefile = 'sciensano_hosp.csv'
    filename = path+name_basefile 
    update_hosp_mean = request_fetchone('SELECT * FROM parameters WHERE name = ?', auto_keys('parameters'), ('hospi_mean_file',))
    mean_in_db = request_fetchall('SELECT * FROM means', auto_keys('means'))
    #mean_in_db = []
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
        db.commit()
        return belgium_mean
    belgium_mean = pd.DataFrame(columns=['DATE', 'NEW_IN'])
    for dico in mean_in_db:
        belgium_mean = belgium_mean.append({'DATE':dico['date'], 'NEW_IN':float(dico['value'])}, ignore_index=True)
    return belgium_mean

"""
    # check si on a deja les dernieres donnees d'hospi reelles
def get_mean_hospi():
    db = get_db()
    path = 'data/Hospi_numbers/'
    name_basefile = 'sciensano_hosp.csv'
    filename = path+name_basefile 
    mean_hospi_filename = path+'hospi_mean.csv'
    update_hosp_mean = request_fetchone('SELECT * FROM parameters WHERE name = ?', auto_keys('parameters'), ('hospi_mean_file',))
    if update_hosp_mean is None or update_hosp_mean['value'] != datetime.date.today().strftime('%Y-%m-%d') or not os.path.isfile(mean_hospi_filename):
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
        belgium_mean.to_csv(mean_hospi_filename)
        if update_hosp_mean is None:
            insert_or_update('INSERT INTO parameters (name, value) VALUES (?, ?)', ('hospi_mean_file', datetime.date.today().strftime('%Y-%m-%d')))
        else:
            insert_or_update('UPDATE parameters SET value = ? WHERE name = ?', (datetime.date.today().strftime('%Y-%m-%d'), 'hospi_mean_file'))
        db.commit()
        return belgium_mean
    return pd.read_csv(mean_hospi_filename)
"""