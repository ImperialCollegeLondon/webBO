from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, flash, make_response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from . import db 
import json
from .models import Data, Experiment
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly
from summit.benchmarks import get_pretrained_reizman_suzuki_emulator
from summit.utils.dataset import DataSet
from .bo_integration import run_bo, rerun_bo


home_dash = Blueprint("home_dash", __name__)


@home_dash.route("/", methods=["GET", "POST"])
@login_required
def home():
    if request.method == "POST":
        if request.form['action'] == "add-dataset":
            if Data.query.count() == 3:
                flash("Whoops! You cannot have more than 3 datasets uploaded. Please export and delete at least one dataset in your repository.", category="error")
            else:
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
        elif request.form['action'] == "add-sample-dataset":
            please_add_sample_dataset()
            return redirect(url_for("home_dash.home"))
        elif "remove-dataset-" in request.form['action']:
            note = Data.query.get(int(request.form['action'].removeprefix("remove-dataset-")))
            db.session.delete(note)
            db.session.commit()
        elif "remove-experiment-" in request.form['action']:
            note = Experiment.query.get(int(request.form['action'].removeprefix("remove-experiment-")))
            db.session.delete(note)
            db.session.commit()
        elif request.form['action'] == "logout":
            return redirect(url_for("auth.logout"))

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
    
    elif False:
        fig = go.Figure([
            go.Scatter(x=list(data['iteration']), y=list(data[list(data.columns)[int(expt_info.target)]])),
            go.Scatter(x=list(recs['iteration']), y=list(recs[list(recs.columns)[int(expt_info.target)]]), name='predicted measurements'),
        ])
    else:
        fig = go.Figure([
            go.Scatter(x=df['iteration'], y=df[list(data.columns)[int(expt_info.target)]]),
        ])

    fig.update_layout(
        xaxis_title="iteration",
        yaxis_title=f"{target_column_name}",
        legend_title="Legend Title",
        font=dict(
            family="Courier New, monospace",
            size=18,
            color="RebeccaPurple"
        ),
        autotypenumbers='convert types'
    )

    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    if request.method == "POST":
        if request.form['action'] == "view-my-stuff":
            return redirect(url_for('home_dash.home'))
        if request.form['action'] == 'run':
            recs, campaign = run_bo(expt, expt.target, batch_size=expt.batch_size)
            recs['iteration'] = df['iteration'].max() + 1
            expt.next_recs = recs.to_json()
            expt.iterations_completed = expt.iterations_completed + 1
            expt.data = df.to_json(orient='records')
            db.session.add(expt)
            db.session.flush()
            db.session.commit()
            return redirect(url_for('experiment_forms.run_expt', expt_name=expt.name))
        elif request.form['action'] == 'add':
            return redirect(url_for('experiment_forms.add_measurements', expt_name=expt.name))
        elif request.form['action'] == 'send':
            return redirect(url_for('dataset_forms.send', expt_name=expt.name))
        elif request.form['action'] == 'download':
            print('hello')
            csv = df.to_csv(index=False)

            # Create response
            response = make_response(csv)
            response.headers['Content-Disposition'] = f'attachment; filename={expt_name}.csv'
            response.headers['Content-Type'] = 'text/csv'

            return response

    return render_template(
        'view_experiment.html',
        user=current_user,
        expt_name=expt.name, # session['viewexpt'],
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
    if request.method == "POST":
        if request.form['action'] == "view-my-stuff":
            return redirect(url_for('home_dash.home'))
        if request.form['action'] == 'setup-experiment':
            variable_types={
                "catalyst": {"parameter-type":"cat",
                            "json": '[{"catalyst":"P1-L1"},{"catalyst":"P2-L1"},{"catalyst":"P1-L2"},{"catalyst":"P1-L3"}, {"catalyst":"P1-L4"},{"catalyst":"P1-L5"},{"catalyst":"P1-L6"},{"catalyst":"P1-L7"}]',
                },
                "t_res": {"parameter-type": "cont", "min": 60.0, "max": 600.0},
                "temperature": {"parameter-type": "cont", "min": 30.0, "max": 110.0},
                "catalyst_loading": {"parameter-type": "cont", "min": 0.5, "max": 2.5},
                "yield": {"parameter-type": "cont", "min": 0.0, "max": 100.0},
            }
            sample_experiment = Experiment(
                name="sample-reizman-suzuki",
                dataset_name="sample-reizman-suzuki",
                data=df.to_json(orient="records"),
                target=4,
                variables=json.dumps(variable_types),
                kernel="Matern",
                acqFunc="Expected Improvement",
                opt_type="maximize",
                batch_size=1,
                next_recs=pd.DataFrame().to_json(orient="records"),
                iterations_completed=0,
                user_id=current_user.id,
            )
            db.session.add(sample_experiment)
            db.session.flush()
            db.session.commit()
            return redirect(url_for('home_dash.view_experiment', expt_name="sample-reizman-suzuki"))
    return render_template(
        'view_dataset.html',
        user=current_user,
        name=session['viewdata'],
        tables=[df.to_html(classes='data', index=False)],
        titles=df.columns.values,
        summaries=[df.describe().to_html(classes='data', index=True)],
        summary_titles=df.describe().columns.values,
    )


@home_dash.route('/add-sample-dataset', methods=['POST'])
def add_sample_dataset():
    sample_dataset = {
        "catalyst": ["P1-L3"], "t_res": [600], "temperature": [30],"catalyst_loading": [0.498],
    }
    
    dataset_df = pd.DataFrame(sample_dataset)

    emulator = get_pretrained_reizman_suzuki_emulator(case=1)
    conditions = DataSet.from_df(dataset_df)
    emulator_output = emulator.run_experiments(conditions, rtn_std=True)
    rxn_yield = emulator_output.to_numpy()[0, 5]
    
    dataset_df['yield'] = rxn_yield*100
    dataset_df['iteration'] = 0
    print(dataset_df)
    variable_df = pd.DataFrame(dataset_df.columns, columns=["variables"])
    sample_data = Data(
        name="sample-reizman-suzuki",
        data=dataset_df.to_json(orient="records"),
        variables=variable_df.to_json(orient="records"),
        user_id=current_user.id,
    )
    db.session.add(sample_data)
    db.session.flush()
    db.session.commit()
    return jsonify({})


def please_add_sample_dataset():
    sample_dataset = {
        "catalyst": ["P1-L3"], "t_res": [600], "temperature": [30],"catalyst_loading": [0.498],
    }
    
    dataset_df = pd.DataFrame(sample_dataset)

    emulator = get_pretrained_reizman_suzuki_emulator(case=1)
    conditions = DataSet.from_df(dataset_df)
    emulator_output = emulator.run_experiments(conditions, rtn_std=True)
    rxn_yield = emulator_output.to_numpy()[0, 5]
    
    dataset_df['yield'] = rxn_yield*100
    dataset_df['iteration'] = 0
    print(dataset_df)
    variable_df = pd.DataFrame(dataset_df.columns, columns=["variables"])
    sample_data = Data(
        name="sample-reizman-suzuki",
        data=dataset_df.to_json(orient="records"),
        variables=variable_df.to_json(orient="records"),
        user_id=current_user.id,
    )
    db.session.add(sample_data)
    db.session.flush()
    db.session.commit()


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
