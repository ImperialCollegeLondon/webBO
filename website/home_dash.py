from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from . import db 
import json
from .models import Data, Experiment
import pandas as pd
from dash import Dash, html, dcc


home_dash = Blueprint("home_dash", __name__)


@home_dash.route("/", methods=["GET", "POST"])
@login_required
def home():
    if request.method == "POST":
        print(type(request.form['action']))
        if request.form['action'] == "add-dataset":
            return redirect(url_for("dataset_forms.select_upload_method"))
        elif request.form['action'] == "add-experiment":
            return redirect(url_for("experiment_forms.setup"))
        elif "viewdata-" in request.form['action']:
            session['viewdata'] = request.form['action'].removeprefix('viewdata-')
            return redirect(url_for("home_dash.view_dataset"))
        elif "viewexpt-" in request.form['action']:
            session['viewexpt'] = request.form['action'].removeprefix('viewexpt-')
            return redirect(url_for("home_dash.view_experiment"))
        elif request.form['action'] == "explore":
            print(request.form['action'])
            print('working?')

    return render_template("home.html", user=current_user)


@home_dash.route("/view_experiment", methods=["POST", "GET"])
@login_required
def view_experiment():
    # Load your DataFrame (df) and other relevant data
    df = [pd.read_json(row.data) for row in Experiment.query.filter_by(name=session['viewexpt']).all()][0]
    expt = [row for row in Experiment.query.filter_by(name=session['viewexpt']).all()][0]
    print(expt.variables)
    # Highlight the desired column (e.g., "MyColumn")
    df['target'] = df['target'].apply(lambda x: f'{x}')

    return render_template(
        'view_experiment.html',
        user=current_user,
        expt_name=session['viewexpt'],
        dataset_name=expt.dataset_name,
        target_name='target',
        df=df,  # Pass the modified DataFrame directly
        titles=df.columns.values,
    )


@home_dash.route("/view_dataset", methods=["POST", "GET"])
@login_required
def view_dataset():
    df = [pd.read_json(row.data) for row in Data.query.filter_by(name=session['viewdata']).all()][0]
    print(df.describe())
    return render_template(
        'view_dataset.html',
        user=current_user,
        name=session['viewdata'],
        tables=[df.to_html(classes='data', index=False)],
        titles=df.columns.values,
        summaries=[df.describe().to_html(classes='data', index=True)],
        summary_titles=df.describe().columns.values,
    )


@home_dash.route('/delete-dataset', methods=['POST'])
def delete_dataset():
    data = json.loads(request.data)
    noteId = data['noteId']
    note = Data.query.get(noteId)
    if note:
        if note.user_id == current_user.id:
            db.session.delete(note)
            db.session.commit()
    return jsonify({})


@home_dash.route('/delete-experiment', methods=['POST'])
def delete_experiment():
    data = json.loads(request.data)
    noteId = data['noteId']
    note = Experiment.query.get(noteId)
    if note:
        if note.user_id == current_user.id:
            db.session.delete(note)
            db.session.commit()
    return jsonify({})
