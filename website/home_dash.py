from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, flash, make_response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from . import db 
import re
import json
from .models import Data, Experiment, Target
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly
from flask import session
from summit.benchmarks import get_pretrained_reizman_suzuki_emulator
from summit.utils.dataset import DataSet
from .bo_integration import run_bo, rerun_bo, run_mobo


home_dash = Blueprint("home_dash", __name__)




@home_dash.route('/tutorial', methods=['GET'])
@login_required
def tutorial():
    return render_template('tutorial.html', user=current_user)

@home_dash.route('/video_tutorial', methods=['GET'])
@login_required
def video_tutorial():
    return render_template('video_tutorial.html', user=current_user)

@home_dash.route('/explanations', methods=['GET'])
@login_required
def explanations():
    return render_template('explanations.html', user=current_user)


@home_dash.route("/", methods=["GET", "POST"])
@login_required
def home():
    if request.method == "POST":
        if request.form['action'] == "add-dataset":
            if Data.query.count() == 3:
                flash("Whoops! You cannot have more than 3 datasets uploaded. Please export and delete at least one dataset in your repository.", category="error")
            else:
                experiment_type = request.form.get("experiment_type")
                if experiment_type == "single":
                    return redirect(url_for("experiment_forms.setup"))
                elif experiment_type == "multi":
                    return redirect(url_for("experiment_forms.setup_mo"))
                return redirect(url_for("dataset_forms.select_upload_method"))
        elif request.form['action'] == "add-experiment":
            if not db.session.query(Data).all():
                flash("Whoops! You need to upload a dataset first!", category="error")
            else:
                experiment_type = request.form.get("experiment_type")
                if experiment_type == "single":
                    return redirect(url_for("experiment_forms.setup"))
                elif experiment_type == "multi":
                    return redirect(url_for("experiment_forms.setup_mo"))       
        elif "viewdata-" in request.form['action']:
            session['viewdata'] = request.form['action'].removeprefix('viewdata-')
            return redirect(url_for("home_dash.view_dataset"))
        elif "viewexpt-" in request.form['action']:
            session['viewexpt'] = request.form['action'].removeprefix('viewexpt-')
            return redirect(url_for("home_dash.view_experiment", expt_name=request.form['action'].removeprefix('viewexpt-')))
        elif request.form['action'] == "add-sample-dataset":
            sample_dataset_name = request.form.get('sample-dataset-name')
            if sample_dataset_name == "sample-reizman-suzuki":
                flash("Please select another name and try again.", category="error")
            else:
                please_add_sample_dataset(sample_dataset_name)
            return redirect(url_for("home_dash.home"))
        
        elif request.form['action'] == "add-sample-dataset-mo":
            sample_dataset_name = request.form.get('sample-dataset-name')
            if sample_dataset_name == "sample-reizman-suzuki-mo":  
                flash("Please select another name and try again.", category="error")
            else:
                please_add_sample_dataset_mo(sample_dataset_name) 
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
        elif request.form['action'] == "reset-user":
            Data.query.filter_by(user_id=current_user.id).delete()
            Experiment.query.filter_by(user_id=current_user.id).delete()

    return render_template("home.html", user=current_user)



@home_dash.route("/view_experiment_original/<string:expt_name>", methods=["POST", "GET"])
@login_required
def view_experiment_original(expt_name):
   
    
    expt = [row for row in Experiment.query.filter_by(name=expt_name).all()][0]
    data_info = Data.query.filter_by(name=expt.dataset_name).first()
    targets = Target.query.filter_by(experiment_id=expt.id).all()
    df = pd.read_json(expt.data)
    variable_list = list(df.columns)
    target_column_names=[]
    target_indices=[]
    target_opt_types = []
    target_weights = []
    expt_info = expt
    
    for target in targets:
        target_column_names.append(variable_list[target.index])  
        target_indices.append(int(target.index))
        target_opt_types.append(target.opt_type)
        target_weights.append(float(target.weight))
    
    print("Targets:", target_column_names)  
    print("Target indices:", target_indices)  

    for col in target_column_names:
        df[col] = df[col].apply(lambda x: f'{x}')

    def is_numeric(val):
        return bool(re.fullmatch(r"^-?\d*\.?\d+$", str(val)))

    df_float = df.copy()
    for col in target_column_names:
        df_float[col] = [float(val) if is_numeric(val) else val for val in df[col]]

    recs = pd.read_json(expt.next_recs)
    graphs = {}

    for target_name in target_column_names:
        fig = go.Figure([
            go.Scatter(x=df['iteration'], y=df_float[target_name], mode='markers', name=f'{target_name.title()} vs Iteration')
        ])
    
        fig.update_layout(
            xaxis_title="Iteration",
            yaxis_title=f"{target_name.title()}",
            title=f"{target_name.title()} vs Iteration",
            font=dict(
                family="Courier New, monospace",
                size=18,
                color="RebeccaPurple"
            ),
            autotypenumbers='convert types',
            height=600,  
            width=900,  
            autosize=True
        )

        graphs[target_name] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    pairwise_graphs = {}

    for i in range(len(target_column_names)):
        for j in range(i + 1, len(target_column_names)):  # Avoid duplicate pairs
            target_x, target_y = target_column_names[i], target_column_names[j]

            fig = go.Figure([
                go.Scatter(x=df_float[target_x], y=df_float[target_y], mode='markers', name=f'{target_x.title()} vs {target_y.title()}')
            ])

            fig.update_layout(
                xaxis_title=f"{target_x.title()}",
                yaxis_title=f"{target_y.title()}",
                    title=f"{target_x.title()} vs {target_y.title()}",
                font=dict(
                    family="Courier New, monospace",
                    size=18,
                    color="RebeccaPurple"
                ),
                height=600,  
                width=900,  
                autosize=True
            )

            pairwise_graphs[f"{target_x}_{target_y}"] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    if request.method == "POST":
        if request.form['action'] == "view-my-stuff":
            return redirect(url_for('home_dash.home'))
        if request.form['action'] == 'run':
        
            if expt_info.objective == "SINGLE":
                # sobo
                recs, campaign = run_bo(expt,  target=target_indices, opt_type=target_opt_types,  batch_size=expt.batch_size)
            else:
                # mobo
                recs, campaign = run_mobo(
                    expt, 
                    targets=target_indices, 
                    
                    opt_types=target_opt_types, 

                    weights = target_weights,
                    
                    batch_size=expt.batch_size
                )

            recs['iteration'] = df['iteration'].max() + 1
            expt.next_recs = recs.to_json()
            print(expt.next_recs)
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
        target_names=target_column_names,
        df=df,  
        df_float = df_float,
        titles=df.columns.values,
        graphs = graphs,
        pairwise_graphs = pairwise_graphs
    )





@home_dash.route("/view_experiment/<string:expt_name>", methods=["POST", "GET"])
@login_required
def view_experiment(expt_name):
   
    
    expt = [row for row in Experiment.query.filter_by(name=expt_name).all()][0]
    data_info = Data.query.filter_by(name=expt.dataset_name).first()
    targets = Target.query.filter_by(experiment_id=expt.id).all()
    df = pd.read_json(expt.data)
    variable_list = list(df.columns)
    target_column_names=[]
    target_indices=[]
    target_opt_types = []
    target_weights = []
    expt_info = expt
    
    for target in targets:
        target_column_names.append(variable_list[target.index])  
        target_indices.append(int(target.index))
        target_opt_types.append(target.opt_type)
        target_weights.append(float(target.weight))
    
    print("Targets:", target_column_names)  
    print("Target indices:", target_indices)  

    for col in target_column_names:
        df[col] = df[col].apply(lambda x: f'{x}')

    recs = pd.read_json(expt.next_recs)

    if request.method == "POST":
        if request.form['action'] == "view-my-stuff":
            return redirect(url_for('home_dash.home'))
        if request.form['action'] == 'run':
        
            if expt_info.objective == "SINGLE":
                # sobo
                recs, campaign = run_bo(expt,  target=target_indices, opt_type=target_opt_types,  batch_size=expt.batch_size)
            else:
                # mobo
                recs, campaign = run_mobo(
                    expt, 
                    targets=target_indices, 
                    
                    opt_types=target_opt_types, 

                    weights = target_weights,
                    
                    batch_size=expt.batch_size
                )

            recs['iteration'] = df['iteration'].max() + 1
            expt.next_recs = recs.to_json()
            print(expt.next_recs)
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
            csv = df.to_csv(index=False)
            

        
            response = make_response(csv)
            response.headers['Content-Disposition'] = f'attachment; filename={expt_name}.csv'
            response.headers['Content-Type'] = 'text/csv'

            return response

    return render_template(
        'view_experiment.html',
        user=current_user,
        expt_name=expt.name, 
        dataset_name=expt.dataset_name,
        target_names=target_column_names,
        df=df,  
        titles=df.columns.values,
    )


@home_dash.route("/get_plot_data", methods=["GET"])
@login_required
def get_plot_data():
    x_var = request.args.get("x_var")
    y_var = request.args.get("y_var")

    if not x_var or not y_var:
        return jsonify({"error": "Invalid selection"}), 400

    expt_name = request.args.get("expt_name") 
    expt = Experiment.query.filter_by(name=expt_name).first()
    
    if not expt:
        return jsonify({"error": "Experiment not found"}), 404

    df = pd.read_json(expt.data)

    def is_numeric(val):
        return bool(re.fullmatch(r"^-?\d*\.?\d+$", str(val)))

    df_float = df.copy()
    for col in df.columns:
        df_float[col] = [float(val) if is_numeric(val) else val for val in df[col]]

    if x_var not in df_float.columns or y_var not in df_float.columns:
        return jsonify({"error": "Selected variables not found"}), 400

  
    fig = go.Figure([
        go.Scatter(x=df_float[x_var], y=df_float[y_var], mode='markers', 
                   name=f'{x_var.title()} vs {y_var.title()}')
    ])

    fig.update_layout(
        xaxis_title=f"{x_var.title()}",
        yaxis_title=f"{y_var.title()}",
        title=f"{x_var.title()} vs {y_var.title()}",
        font=dict(family="Courier New, monospace", size=18, color="RebeccaPurple"),
        height=600,
        width=900,
        autosize=True
    )

    return jsonify({"graph": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)})




@home_dash.route("/view_dataset", methods=["POST", "GET"])
@login_required
def view_dataset():
    df = [pd.read_json(row.data) for row in Data.query.filter_by(name=session['viewdata']).all()][0]
    print(df.describe())
    if request.method == "POST":
        if request.form['action'] == "view-my-stuff":
            return redirect(url_for('home_dash.home'))
        if request.form['action'] == 'download':
            csv = df.to_csv(index=False)
            # Create response
            response = make_response(csv)
            
            response.headers['Content-Disposition'] = f"attachment; filename={session['viewdata']}.csv"

            response.headers['Content-Type'] = 'text/csv'

            return response
        if request.form['action'] == 'setup-experiment':
            existing_experiment = Experiment.query.filter_by(name=session['viewdata']).first()
            
            
            if existing_experiment:
                print(f"Experiment with name {session['viewdata']} already exists.")
                return redirect(url_for('home_dash.view_experiment', expt_name=f"{session['viewdata']}"))


            if session['viewdata'].endswith("-sample-reizman"):
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
                    name=f"{session['viewdata']}",
                    dataset_name=f"{session['viewdata']}",
                    data=df.to_json(orient="records"),
                    objective = 'SINGLE',
                    fidelity = 'SINGLE',
                    n_targets = 1,
                    variables=json.dumps(variable_types),
                    kernel="Matern",
                    acqFunc="Expected Improvement",
                    batch_size=1,
                    next_recs=pd.DataFrame().to_json(orient="records"),
                    iterations_completed=0,
                    user_id=current_user.id,
                )
                db.session.add(sample_experiment)
                db.session.flush()
                db.session.commit()

                targets = Target(
                    index = 4,
                    name = 'yield',
                    opt_type = "MAX", 
                    weight = float(1.0),
                    experiment_id = sample_experiment.id
                )
                db.session.add(targets)
                db.session.commit()
                print('printing tagets relationship',sample_experiment.targets)

                return redirect(url_for('home_dash.view_experiment', expt_name=f"{session['viewdata']}"))
            elif session['viewdata'].endswith("-sample-reizman-mo"):
                variable_types={
                    "catalyst": {"parameter-type":"cat",
                            "json": '[{"catalyst":"P1-L1"},{"catalyst":"P2-L1"},{"catalyst":"P1-L2"},{"catalyst":"P1-L3"}, {"catalyst":"P1-L4"},{"catalyst":"P1-L5"},{"catalyst":"P1-L6"},{"catalyst":"P1-L7"}]',
                    },
                    "t_res": {"parameter-type": "cont", "min": 60.0, "max": 600.0},
                    "temperature": {"parameter-type": "cont", "min": 30.0, "max": 110.0},
                    "catalyst_loading": {"parameter-type": "cont", "min": 0.5, "max": 2.5},
                    "yield": {"parameter-type": "cont", "min": 0.0, "max": 100.0},
                    "ton": {"parameter-type": "cont", "min": 0.0, "max": 100.0}
                }
                sample_experiment = Experiment(
                    name=f"{session['viewdata']}",
                    dataset_name=f"{session['viewdata']}",
                    data=df.to_json(orient="records"),
                    objective = 'MULTI',
                    fidelity = 'SINGLE',
                    n_targets = 2,
                    variables=json.dumps(variable_types),
                    kernel="Matern",
                    acqFunc="Expected Improvement",
                    batch_size=1,
                    next_recs=pd.DataFrame().to_json(orient="records"),
                    iterations_completed=0,
                    user_id=current_user.id,
                )
                db.session.add(sample_experiment)
                db.session.flush()
                db.session.commit()

                targets = [
                    Target(index = 4, 
                           name = 'yield', 
                           opt_type = "MAX", 
                           weight = float(1.0), 
                           experiment_id = sample_experiment.id),
                           
                    Target(index = 5, 
                           name = 'ton', 
                           opt_type = "MAX", 
                           weight = float(1.0), 
                           experiment_id = sample_experiment.id)
                ]
                db.session.add_all(targets)
                db.session.commit()
                print('printing tagets relationship',sample_experiment.targets)
                
                return redirect(url_for('home_dash.view_experiment', expt_name=f"{session['viewdata']}"))
    return render_template(
        'view_dataset.html',
        user=current_user,
        name=session['viewdata'],
        tables=[df.to_html(classes='data', index=False)],
        titles=df.columns.values,
        summaries = [df.drop(columns=['iteration']).describe().to_html(classes='data', index=True)], #removing iteration column from summary statistics
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


def please_add_sample_dataset(name):
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
        name=f"{name}-sample-reizman", #"sample-reizman-suzuki",
        data=dataset_df.to_json(orient="records"),
        variables=variable_df.to_json(orient="records"),
        user_id=current_user.id,
    )
    db.session.add(sample_data)
    db.session.flush()
    db.session.commit()



def add_sample_dataset_mo():
    sample_dataset = {
        "catalyst": ["P1-L3"], "t_res": [600], "temperature": [30],"catalyst_loading": [0.498],
    }
    
    dataset_df = pd.DataFrame(sample_dataset)

    emulator = get_pretrained_reizman_suzuki_emulator(case=1)
    conditions = DataSet.from_df(dataset_df)
    emulator_output = emulator.run_experiments(conditions, rtn_std=True)
    rxn_yield = emulator_output.to_numpy()[0, 5]
    rxn_ton = emulator_output.to_numpy()[0, 6]
    
    dataset_df['yield'] = rxn_yield*100
    dataset_df['TON'] = rxn_ton*100
    dataset_df['iteration'] = 0
    print(dataset_df)
    variable_df = pd.DataFrame(dataset_df.columns, columns=["variables"])
    sample_data = Data(
        name="sample-reizman-suzuki-mo",
        data=dataset_df.to_json(orient="records"),
        variables=variable_df.to_json(orient="records"),
        user_id=current_user.id,
    )
    db.session.add(sample_data)
    db.session.flush()
    db.session.commit()
    return jsonify({})


def please_add_sample_dataset_mo(name):
    sample_dataset = {
        "catalyst": ["P1-L3"], "t_res": [600], "temperature": [30],"catalyst_loading": [0.498],
    }

    dataset_df = pd.DataFrame(sample_dataset)

    emulator = get_pretrained_reizman_suzuki_emulator(case=1)
    conditions = DataSet.from_df(dataset_df)
    emulator_output = emulator.run_experiments(conditions, rtn_std=True)
    print('emulator ourput:',emulator_output.to_numpy())
    rxn_yield = emulator_output.to_numpy()[0, 5]
    rxn_ton = emulator_output.to_numpy()[0, 4]

    dataset_df['yield'] = rxn_yield*100
    dataset_df['ton'] = rxn_ton*10 # check this
    dataset_df['iteration'] = 0
    print(dataset_df)
    variable_df = pd.DataFrame(dataset_df.columns, columns=["variables"])
    sample_data = Data(
        name=f"{name}-sample-reizman-mo", #"sample-reizman-suzuki-mo",
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
