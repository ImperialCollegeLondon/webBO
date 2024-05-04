from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from . import db 
import json
from .models import Data, Experiment
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly


home_dash = Blueprint("home_dash", __name__)


@home_dash.route("/", methods=["GET", "POST"])
@login_required
def home():
    if request.method == "POST":
        print(type(request.form['action']))
        if request.form['action'] == "add-dataset":
            return redirect(url_for("dataset_forms.select_upload_method"))
        elif request.form['action'] == "add-experiment":
            if not db.session.query(Data).all():
                flash("Whoops! You need to upload a dataset first!", category="error")
            else:
                return redirect(url_for("experiment_forms.setup"))
        elif "viewdata-" in request.form['action']:
            session['viewdata'] = request.form['action'].removeprefix('viewdata-')
            return redirect(url_for("home_dash.view_dataset"))
        elif "viewexpt-" in request.form['action']:
            session['viewexpt'] = request.form['action'].removeprefix('viewexpt-')
            return redirect(url_for("home_dash.view_experiment", expt_name=request.form['action'].removeprefix('viewexpt-')))
        elif request.form['action'] == "explore":
            print(request.form['action'])
            print('working?')

    return render_template("home.html", user=current_user)


@home_dash.route("/view_experiment/<string:expt_name>", methods=["POST", "GET"])
@login_required
def view_experiment(expt_name):
    # Load your DataFrame (df) and other relevant data
    # df = [pd.read_json(row.data) for row in Experiment.query.filter_by(name=expt_name).all()][0]
    expt = [row for row in Experiment.query.filter_by(name=expt_name).all()][0]
    data_info = Data.query.filter_by(name=expt.dataset_name).first()
    df = pd.read_json(expt.data) # pd.read_json(data_info.data)
    variable_list = list(df.columns)
    target_column_name = variable_list[int(expt.target)]
    # Highlight the desired column (e.g., "MyColumn")
    df[target_column_name] = df[target_column_name].apply(lambda x: f'{x}')

    expt_info = expt
    recs = pd.read_json(expt.next_recs)
    data = df

    variable_list = list(data.columns)
    target_column_name = variable_list[int(expt_info.target)]

    if len(recs.columns) < 1:
        fig = go.Figure([
            go.Scatter(x=list(data['iteration']), y=list(data[list(data.columns)[int(expt_info.target)]])),
            ])
    else:
        fig = go.Figure([
            go.Scatter(x=list(data['iteration']), y=list(data[list(data.columns)[int(expt_info.target)]])),
            go.Scatter(x=list(recs['iteration']), y=list(recs[list(recs.columns)[int(expt_info.target)]]), name='predicted measurements'),
        ])
    fig.update_layout(
        xaxis_title="iteration",
        yaxis_title=f"{target_column_name}",
        legend_title="Legend Title",
        font=dict(
            family="Courier New, monospace",
            size=18,
            color="RebeccaPurple"
        )
    )

    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    if request.method == "POST":
        if request.form['action'] == 'run':
            return redirect(url_for('experiment_forms.run_expt', expt_name=expt.name))
        elif request.form['action'] == 'add':
            return redirect(url_for('experiment_forms.add_measurements', expt_name=expt.name))

    return render_template(
        'view_experiment.html',
        user=current_user,
        expt_name=session['viewexpt'],
        dataset_name=expt.dataset_name,
        target_name=target_column_name,
        df=df,  # Pass the modified DataFrame directly
        titles=df.columns.values,
        graphJSON=graphJSON,
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
