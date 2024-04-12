from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, session
from flask_login import login_required, current_user
from .models import Data, Experiment
from . import db 
import json
import pandas as pd
from werkzeug.utils import secure_filename
import werkzeug
# from . import bo_integration
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FormField, HiddenField, SubmitField
from wtforms.validators import DataRequired, InputRequired


expt_views = Blueprint("experiment_forms", __name__)


class DatasetSelectionForm(FlaskForm):
    form_name = HiddenField("form_name")
    name = StringField('experiment name', validators=[DataRequired()], id='experiment_name')
    dataset = SelectField('dataset', coerce=str, validators=[DataRequired()], id='dataset_name')
    target = SelectField('target', coerce=str, validators=[DataRequired()], id='target_name')
    submit = SubmitField('Submit dataset')


#class ParameterSpaceForm(FlaskForm):
#    variable = SelectField('variable', coerce=str, validators=[InputRequired()])


class HyperparameterForm(FlaskForm):
    kernel = SelectField('GP kernel type', id='kernel')
    acqFunc = SelectField('Acquisition Function type', id='acqFunc')
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
    data_form.dataset.choices = [(row.id, row.name) for row in Data.query.all()]
    data_form.target.choices = [(row.id, row.variables) for row in Data.query.all()]
    expt_names = [row.name for row in Experiment.query.all()]
    print(expt_names)
    if data_form.name.data in expt_names:
        flash("That name already exists!", category="error")
    print(data_form.name.data)

    hyp_form = HyperparameterForm()
    hyp_form.kernel.choices = ['Matern', 'Tanimoto']
    hyp_form.acqFunc.choices = ['Expected Improvement', 'Probability of Improvement']
    hyp_form.opt_type.choices = ['maximize', 'minimize']

    if request.method == "POST":
        if data_form.name.data == str:
            print('OMGGGGGG')
        if request.form.get('expt_btn') == "run-expt":
            dataset_info = [row for row in Data.query.filter_by(id=data_form.dataset.data).all()]
            variable_types = {}
            for index, variable in pd.read_json(dataset_info[0].variables).iterrows():
                col = variable['variables']
                print(col)
                print(request.form.get(f"parameterspace-{col}"))
                
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
                        df = pd.read_csv(filename)
                    variable_types[f"{col}"] = {
                        "parameter-type": request.form.get(f"parameterspace-{col}"),
                        "json": df.to_json(orient="records"),
                        "encoding": request.form.get(f"new-elements-subs-{col}"),
                    }
                elif request.form.get(f"parameterspace-{col}") == "int":
                    variable_types[f"{col}"] = {
                        "parameter-type": request.form.get(f"parameterspace-{col}"),
                        "min": int(request.form.get(f'min-vals-{col}')),
                        "max": int(request.form.get(f"max-vals-{col}")),
                    }
                elif request.form.get(f"parameterspace-{col}") == "cont":
                    variable_types[f"{col}"] = {
                        "parameter-type": request.form.get(f"parameterspace-{col}"),
                        "min": float(request.form.get(f'min-vals-{col}')),
                        "max": float(request.form.get(f"max-vals-{col}")),
                    }
            expt_info = Experiment(
                name=data_form.name.data,
                dataset_name=dataset_info[0].name,
                data=dataset_info[0].data,
                variables=json.dumps(variable_types),
                kernel=hyp_form.kernel.data,
                acqFunc=hyp_form.acqFunc.data,
                opt_type=hyp_form.opt_type.data,
                user_id=current_user.id,
            )
            db.session.add(expt_info)
            db.session.flush()
            db.session.commit()
            flash("Upload successful!", category="success")
            return redirect(url_for('home_dash.home'))

    return render_template(
        "setup_experiment.html",
        user=current_user,
        data_form=data_form,
        hyp_form=hyp_form,
        variable_names=_get_variable_names(),
    )


@expt_views.route("/run_expt", methods=["GET", "POST"])
@login_required
def run_expt():
    pass


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
