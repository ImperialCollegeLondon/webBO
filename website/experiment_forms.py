from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, session, Flask
from flask_login import login_required, current_user
from .models import Data, Experiment
from . import db 
import json
import pandas as pd
from werkzeug.utils import secure_filename
import werkzeug
# from . import bo_integration
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FormField, HiddenField, SubmitField, IntegerField
from wtforms.validators import DataRequired, InputRequired
from .bo_integration import run_bo, rerun_bo
from summit.benchmarks import get_pretrained_reizman_suzuki_emulator
from summit.utils.dataset import DataSet

import plotly.express as px
import plotly.graph_objects as go
import plotly


expt_views = Blueprint("experiment_forms", __name__)


class DatasetSelectionForm(FlaskForm):
    form_name = HiddenField("form_name")
    name = StringField('experiment name', validators=[DataRequired()], id='experiment_name', render_kw={"placeholder": "Enter your experiment name here"})
    dataset = SelectField('dataset', coerce=str, validators=[DataRequired()], id='dataset_name')
    target = SelectField('Target (i.e. what you want to optimize)', coerce=str, validators=[DataRequired()], id='target_name')
    submit = SubmitField('Submit dataset')


#class ParameterSpaceForm(FlaskForm):
#    variable = SelectField('variable', coerce=str, validators=[InputRequired()])


class HyperparameterForm(FlaskForm):
    kernel = SelectField('GP kernel type', id='kernel')
    acqFunc = SelectField('Acquisition Function type', id='acqFunc')
    batch_size = IntegerField('Batch size')
    opt_type = SelectField('Optimization type')
    submit = SubmitField('Submit hyperparameters')


class ExperimentSetupForm(FlaskForm):
    dataset_form = FormField(DatasetSelectionForm)
    hyperparamter_form = FormField(HyperparameterForm)
    submit = SubmitField('Run experiment')


@expt_views.route("/setup", methods=["GET", "POST"])
@login_required
def setup():
    dataset_choices = []
    measurement_choices = {}
    for data in current_user.datas:
        dataset_choices.append(data.name)
        measurement_choices[data.name] = list(pd.read_json(data.variables)['variables'])

    data_form = DatasetSelectionForm(form_name="data_select")
    data_form.dataset.choices = [(row.id, row.name) for row in Data.query.filter_by(user_id=current_user.id)]
    data_form.target.choices = [(row.id, row.variables) for row in Data.query.filter_by(user_id=current_user.id)]
    expt_names = [row.name for row in Experiment.query.filter_by(user_id=current_user.id)]
    if data_form.name.data in expt_names:
        flash("That name already exists!", category="error")

    hyp_form = HyperparameterForm()
    hyp_form.kernel.choices = ['Matern', 'Tanimoto']
    hyp_form.acqFunc.choices = ['Expected Improvement', 'Probability of Improvement']
    hyp_form.opt_type.choices = ['maximize', 'minimize']

    if request.method == "POST":
        # if request.form.get('expt_btn') == "run-expt":
        if 'expt_btn' in request.form:
            dataset_info = [row for row in Data.query.filter_by(id=data_form.dataset.data).all()]
            target = data_form.target.data
            variable_types = {}
            for index, variable in pd.read_json(dataset_info[0].variables).iterrows():
                col = variable['variables']

                if request.form.get(f"parameterspace-{col}") == "cat":
                    datafile = request.files[f"formFile-{col}"]
                    if datafile:
                        filename = secure_filename(datafile.filename)
                        datafile.save(filename)
                        df = pd.read_csv(filename)
                    variable_types[f"{col}"] = {
                        "parameter-type": request.form.get(f"parameterspace-{col}"),
                        "json": df.to_json(orient="records"),
                    }
                elif request.form.get(f"parameterspace-{col}") == "subs":
                    datafile = request.files.get(f"formFile-{col}")
                    if datafile:
                        filename = secure_filename(datafile.filename)
                        datafile.save(filename)
                        df = pd.read_csv(filename, index_col=0)
                    print(request.form.get(f"exampleRadios-{col}"))
                    print(df.to_dict())
                    variable_types[f"{col}"] = {
                        "parameter-type": request.form.get(f"parameterspace-{col}"),
                        "json": df.to_dict()['smiles'],
                        "encoding": request.form.get(f"exampleRadios-{col}"),
                    }
                elif request.form.get(f"parameterspace-{col}") == "int":
                    if int(request.form.get(f"min-vals-{col}")) < int(request.form.get(f"max-vals-{col}")):
                        variable_types[f"{col}"] = {
                            "parameter-type": request.form.get(f"parameterspace-{col}"),
                            "min": int(request.form.get(f'min-vals-{col}')),
                            "max": int(request.form.get(f"max-vals-{col}")),
                        }
                    else:
                        flash('Min values MUST be less than max values.', category="error")
                elif request.form.get(f"parameterspace-{col}") == "cont":
                    if float(request.form.get(f"min-vals-{col}")) < float(request.form.get(f"max-vals-{col}")):
                        variable_types[f"{col}"] = {
                            "parameter-type": request.form.get(f"parameterspace-{col}"),
                            "min": float(request.form.get(f'min-vals-{col}')),
                            "max": float(request.form.get(f"max-vals-{col}")),
                        }
                    else:
                        flash('Min values MUST be less than max values.', category="error")
            print(variable_types)
            expt_info = Experiment(
                name=data_form.name.data,
                dataset_name=dataset_info[0].name,
                data=dataset_info[0].data,
                target=target,
                variables=json.dumps(variable_types),
                kernel=hyp_form.kernel.data,
                acqFunc=hyp_form.acqFunc.data,
                opt_type=hyp_form.opt_type.data,
                batch_size=hyp_form.batch_size.data,
                next_recs=pd.DataFrame().to_json(orient='records'),
                iterations_completed=0,
                user_id=current_user.id,
            )
            db.session.add(expt_info)
            db.session.flush()
            db.session.commit()
            flash("Upload successful!", category="success")
            return redirect(url_for('home_dash.view_experiment', expt_name=expt_info.name)) # redirect(url_for('experiment_forms.run_expt', expt_name=expt_info.name))

    return render_template(
        "setup_experiment.html",
        user=current_user,
        data_form=data_form,
        hyp_form=hyp_form,
        variable_names=_get_variable_names(),
    )


@expt_views.route("/add_measurements/<string:expt_name>", methods=["GET", "POST"])
@login_required
def add_measurements(expt_name):
    # Load your DataFrame (df) and other relevant data
    df = [pd.read_json(row.data) for row in Experiment.query.filter_by(name=expt_name).all()][0]
    expt_info = [row for row in Experiment.query.filter_by(name=expt_name).all()][0]
    data_info = Data.query.filter_by(name=expt_info.dataset_name).first()
    variable_list = list(df.columns)
    target_column_name = variable_list[int(expt_info.target)]
    recs = pd.read_json(expt_info.next_recs)

    if len(recs.columns) < 1:
        recs = pd.DataFrame(columns=df.columns)
        recs.loc[0] = 'insert'

    if expt_info.name == "sample-reizman-suzuki":
        emulator_status = True
        df4em = recs
        data = df4em.drop(['yield', 'iteration'], axis=1)
        emulator = get_pretrained_reizman_suzuki_emulator(case=1)
        conditions = DataSet.from_df(data)
        emulator_output = emulator.run_experiments(conditions, rtn_std=True)
        emulator_value = emulator_output.to_numpy()[0, 5]

    else:
        emulator_status = False
        emulator_value = None

    if request.method == "POST":
        if request.form['action'] == 'submit_measurements':
            for index, row in recs.iterrows():
                new_measurement = {}
                # concatenate df with the input values from the form
                for column in recs.columns:
                    if column == 'iteration':
                        new_measurement[column] = recs['iteration'].max()
                    else:
                        new_measurement[column] = request.form.get(f"{column}")

                # updte the data entry in the Data DB
                ndf = pd.DataFrame([new_measurement])
                df = pd.concat([df, ndf])

            expt_info.data = df.to_json(orient='records')
            db.session.add(expt_info)
            db.session.flush()
            db.session.commit()

            return redirect(url_for('home_dash.view_experiment', expt_name=expt_info.name))

    return render_template(
        "add_measurements.html",
        user=current_user,
        df=df,
        titles=df.columns.values,
        target_name=target_column_name,
        recs=recs,
        emulator=emulator_status,
        emulator_value=emulator_value,
    )


@expt_views.route("/run_expt/<string:expt_name>", methods=["GET", "POST"])
@login_required
def run_expt(expt_name):
    expt_info = Experiment.query.filter_by(name=expt_name).first()
    data = pd.read_json(expt_info.data)

    recs = pd.read_json(expt_info.next_recs)
    print(recs)
    variable_list = list(data.columns)
    target_column_name = variable_list[int(expt_info.target)]

    fig = go.Figure([
        go.Scatter(x=list(data['iteration']), y=list(data[list(data.columns)[int(expt_info.target)]]), mode = 'markers', name='Experiment(s) run by user'), # EM: adding -- mode = 'markers' -- means only the data points are shown, no lines connecting them
        go.Scatter(x=list(recs['iteration']), y=list(recs[list(recs.columns)[int(expt_info.target)]]), mode = 'markers', name='Expected outcome of recommended experiment(s)'),
    ])
    fig.update_layout(
        xaxis_title="iteration",
        yaxis_title=f"{target_column_name}",
        legend_title="Key",
        font=dict(
            family="Courier New, monospace",
            size=18,
            color="RebeccaPurple"
        )
    )

    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    if request.method == "POST":
        if request.form['action'] == 'add':
            return redirect(url_for("experiment_forms.add_measurements", expt_name=expt_info.name))

    return render_template(
        "run_expt.html", # beneath this is everyting we need to add to html to make it run properly
        user=current_user,
        df=recs.drop(target_column_name, axis=1),
        titles=recs.drop(target_column_name, axis=1).columns.values,
        graphJSON=graphJSON,
        target=list(data.columns)[int(expt_info.target)],   
    )


def _get_variable_names():
    rows = Data.query.all()
    datas = []
    for row in rows:
        variables = list(pd.read_json(row.variables)['variables'])
        target_id = 0
        for variable in variables:
            datas.append((row.id, target_id, variable))
            target_id += 1
    return datas

@expt_views.route('/_get_expt_info', methods=["POST"])
def _get_expt_info():
    data = request.get_json()
    target_name = data['target']
    dataset_name = data['dataset']
    rows = Data.query.filter_by(id=dataset_name).all()
    datas = []
    for row in rows:
        variables = list(pd.read_json(row.variables)['variables'])
        target_id = 0
        for variable in variables:
            datas.append((target_id, variable))
            target_id += 1
    return jsonify(datas)


@expt_views.route('/_get_dataset_info/')
def _get_dataset_info():
    data_name = request.values.get('dataset', '01')
    rows = Data.query.filter_by(id=data_name).all()
    datas = []
    for row in rows:
        variables = list(pd.read_json(row.variables)['variables'])
        target_id = 0
        for variable in variables:
            datas.append((target_id, variable))
            target_id += 1
    return jsonify(datas)
