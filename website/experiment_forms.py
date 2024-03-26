from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, session
from flask_login import login_required, current_user
from .models import Data, Experiment
from . import db 
import json
import pandas as pd
from werkzeug.utils import secure_filename
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


class ParameterSpaceForm(FlaskForm):
    variable = SelectField('variable', coerce=str, validators=[InputRequired()])


class HyperparameterForm(FlaskForm):
    kernel = SelectField('GP kernel type', id='kernel')
    acqFunc = SelectField('Acquisition Function type', id='acqFunc')
    opt_type = SelectField('Optimization type')


class ExperimentSetupForm(FlaskForm):
    dataset_form = FormField(DatasetSelectionForm)
    parameter_space_form = FormField(ParameterSpaceForm)


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

    pspace_form = ParameterSpaceForm()

    hyp_form = HyperparameterForm()
    hyp_form.kernel.choices = ['Matern', 'Tanimoto']
    hyp_form.acqFunc.choices = ['Expected Improvement', 'Probability of Improvement']
    hyp_form.opt_type.choices = ['maximize', 'minimize']

    esf = ExperimentSetupForm(
        dataset_form=data_form,
        parameter_space_form=pspace_form,
    )


    _get_variable_names()
    print(type(_get_variable_names()))
    
    return render_template(
        "setup_experiment.html",
        user=current_user,
        data_form=data_form,
        pspace_form=pspace_form,
        hyp_form=hyp_form,
        variable_names=_get_variable_names(),
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
    return jsonify({'message': "data received successfully"})


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
