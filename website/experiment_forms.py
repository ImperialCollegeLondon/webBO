from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, session, Flask
from flask_login import login_required, current_user
from .models import Data, Experiment, Target
from . import db 
import json
import pandas as pd
from werkzeug.utils import secure_filename
import werkzeug
# from . import bo_integration
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FormField, HiddenField, SubmitField, IntegerField, FieldList, DecimalField
from wtforms.validators import DataRequired, InputRequired
from .bo_integration import run_bo, rerun_bo
from summit.benchmarks import get_pretrained_reizman_suzuki_emulator
from summit.utils.dataset import DataSet

import plotly.express as px
import plotly.graph_objects as go
import plotly


expt_views = Blueprint("experiment_forms", __name__)

class TargetOptimisationForm(FlaskForm):
    target_name = StringField('Target Name', render_kw={"readonly": True})  # Display the target name
    opt_type = SelectField('Optimisation type', choices=[('maximize', 'Maximise'), ('minimize', 'Minimise')])
   

class DatasetSelectionForm(FlaskForm):
    form_name = HiddenField("form_name")
    name = StringField('experiment name', validators=[DataRequired()], id='experiment_name', render_kw={"placeholder": "Enter your experiment name here"})
    dataset = SelectField('dataset', coerce=str, validators=[DataRequired()], id='dataset_name')
    target = SelectField('Target (i.e. what you want to optimise)', coerce=str, validators=[DataRequired()], id='target_name')
    submit = SubmitField('Submit dataset')



class TargetForm(FlaskForm):  
    """Subform for each target selection."""
    target = SelectField('Target', coerce=str, validators=[DataRequired()])
    optimisation = SelectField('Optimisation Type', choices=['maximise', 'minimise'])
    weight = DecimalField('Relative Weight', places=2, validators=[DataRequired()], default=1.0)  # Default weight is 1.0

class DatasetSelectionFormMO(FlaskForm):
    form_name = HiddenField("form_name")
    name = StringField('experiment name', validators=[DataRequired()], id='experiment_name', render_kw={"placeholder": "Enter your experiment name here"})
    dataset = SelectField('dataset', coerce=str, validators=[DataRequired()], id='dataset_name')
    #target = SelectMultipleField('Target(s) (i.e. what you want to optimise)', coerce=str, validators=[DataRequired()], id='target_name')  # Multi-selection
    
    targets = FieldList(FormField(TargetForm), min_entries=1)  

    submit = SubmitField('Submit dataset')


#class ParameterSpaceForm(FlaskForm):
#    variable = SelectField('variable', coerce=str, validators=[InputRequired()])


class HyperparameterForm(FlaskForm):
    kernel = SelectField('GP kernel type', id='kernel')
    acqFunc = SelectField('Acquisition Function type', id='acqFunc')
    batch_size = IntegerField('Batch size')
    opt_type = SelectField('Optimization type')
    submit = SubmitField('Submit hyperparameters')

class HyperparameterFormMO(FlaskForm):
    kernel = SelectField('GP kernel type', id='kernel')
    acqFunc = SelectField('Acquisition Function type', id='acqFunc')
    batch_size = IntegerField('Batch size')

    submit = SubmitField('Submit hyperparameters')


class ExperimentSetupForm(FlaskForm):
    dataset_form = FormField(DatasetSelectionForm)
    hyperparamter_form = FormField(HyperparameterForm)
    submit = SubmitField('Run experiment')

class ObjectiveTypeForm(FlaskForm):
    objective_type = SelectField(
        'Select optimisation type',
        choices=[('single', 'Single Objective'), ('multi', 'Multi Objective')],
        id='objective_type'
    )
    submit = SubmitField('Proceed')


@expt_views.route("/setup", methods=["GET", "POST"])
@login_required
def setup():
    dataset_choices = []
    measurement_choices = {}
    for data in current_user.datas:
        dataset_choices.append(data.name)
        measurement_choices[data.name] = list(pd.read_json(data.variables)['variables'])
    print(measurement_choices)
    data_form = DatasetSelectionForm(form_name="data_select")
    data_form.dataset.choices = [(row.id, row.name) for row in Data.query.filter_by(user_id=current_user.id)]
    data_form.target.choices = [(row.id, row.variables) for row in Data.query.filter_by(user_id=current_user.id)]
    expt_names = [row.name for row in Experiment.query.filter_by(user_id=current_user.id)]
    if data_form.name.data in expt_names:
        flash("That name already exists!", category="error")

    hyp_form = HyperparameterForm()
    hyp_form.kernel.choices = ['Matern', 'Tanimoto']
    hyp_form.acqFunc.choices = ['Expected Improvement', 'Probability of Improvement']
    hyp_form.opt_type.choices = ['maximise', 'minimise']
    opt_type_mapping = {"maximise": "MAX", "minimise": "MIN"}
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
            print('target value:',target)
            

            expt_info = Experiment(
                name=data_form.name.data,
                dataset_name=dataset_info[0].name,
                data=dataset_info[0].data,
                objective = 'SINGLE',
                fidelity = 'SINGLE',
                n_targets = 1,
                variables=json.dumps(variable_types),
                kernel=hyp_form.kernel.data,
                acqFunc=hyp_form.acqFunc.data,
                batch_size=hyp_form.batch_size.data,
                next_recs=pd.DataFrame().to_json(orient='records'),
                iterations_completed=0,
                user_id=current_user.id
            )
            db.session.add(expt_info)
            db.session.flush()
            

            columns = list(variable_types.keys())
            print('name:',columns[int(target)], 'opt type:',opt_type_mapping[hyp_form.opt_type.data])
            print(f"expt_info.id: {expt_info.id} (type: {type(expt_info.id)})")


            target_info = Target(
                    index=int(target),  
                    name=columns[int(target)] ,  
                    opt_type=opt_type_mapping[hyp_form.opt_type.data],  
                    weight = float(1.0),
                    experiment_id=expt_info.id  
                )
            print(target_info)
            db.session.add(target_info)
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



@expt_views.route("/setup_mo", methods=["GET", "POST"])
@login_required
def setup_mo():
    dataset_choices = []
    measurement_choices = {}

    if request.method == "POST":
        num_targets = request.form.get("num_targets")
        if num_targets:
            session["num_targets"] = int(num_targets) 
    else:
        num_targets = session.get("num_targets", 1) 
    
    num_targets = int(num_targets)
    
    for data in current_user.datas:
        dataset_choices.append(data.name)
        measurement_choices[data.name] = list(pd.read_json(data.variables)['variables'])

    data_form = DatasetSelectionFormMO(form_name="data_select")
    data_form.dataset.choices = [(row.id, row.name) for row in Data.query.filter_by(user_id=current_user.id)]
    selected_dataset = data_form.dataset.data
     
    if selected_dataset: 
        dataset_info = Data.query.filter_by(id=selected_dataset, user_id=current_user.id).first()
        if dataset_info:
            try:
                df = pd.read_json(dataset_info.variables)  
                variables = df.get("variables", []).tolist()  
                target_options = [(idx, var) for idx, var in enumerate(variables)]  
                print(f"Target options available: {target_options}")

                data_form.targets = [TargetForm() for _ in range(num_targets)]
                print(f"Number of target forms: {len(data_form.targets)}")

                for target_form in data_form.targets:
                    print(f"Target form: {target_form}")
                    print(f"Target field: {target_form.target}")
                    target_form.target.choices = target_options
                    target_form.optimisation.choices = ['maximise', 'minimise']
                    
                    print(f"Number of target forms: {len(data_form.targets)}")
                    print(f"target choices: {target_form.target.choices}")

            except ValueError as e:
                print(f"JSON error for dataset {dataset_info.id}: {e}")
    


    expt_names = [row.name for row in Experiment.query.filter_by(user_id=current_user.id)]
    if data_form.name.data in expt_names:
        flash("That name already exists!", category="error")

    hyp_form = HyperparameterFormMO()
    hyp_form.kernel.choices = ['Matern', 'Tanimoto']
    hyp_form.acqFunc.choices = ['Expected Improvement', 'Probability of Improvement']
    opt_type_mapping = {"maximise": "MAX", "minimise": "MIN"}
    print(hyp_form)

    if request.method == "POST":
        if 'expt_btn' in request.form:
            dataset_info = [row for row in Data.query.filter_by(id=data_form.dataset.data).all()]
            extracted_targets = []

            for i in range(num_targets):  
                target_value = request.form.get(f'targets[{i}].target')
                optimisation_value = request.form.get(f'targets[{i}].optimisation')
                weight_value = request.form.get(f'targets[{i}].weight')
        
                # store extracted target and optimisation values in a dictionary
                extracted_targets.append({
                    'target': target_value,
                    'optimisation': optimisation_value,
                    'weight': weight_value
                })
    
            print('Extracted targets:', extracted_targets)
            
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
            print('variable types:',variable_types)
            
            expt_info = Experiment(
                name=data_form.name.data,
                dataset_name=dataset_info[0].name,
                objective = 'MULTI',
                fidelity = 'SINGLE',
                data=dataset_info[0].data,
                n_targets = num_targets,
                variables=json.dumps(variable_types),
                kernel=hyp_form.kernel.data,
                acqFunc=hyp_form.acqFunc.data,
                batch_size=hyp_form.batch_size.data,
                next_recs=pd.DataFrame().to_json(orient='records'),
                iterations_completed=0,
                user_id=current_user.id,
            )
            db.session.add(expt_info)
            db.session.flush()
            db.session.commit()
            flash("Upload successful!", category="success")

            
            columns = list(variable_types.keys())
            targets = []
            print()
            for idx, target_data in enumerate(extracted_targets):
                
                index = int(target_data['target'])
                print('index', index)
                print('name',columns[index])
                opt_type = target_data['optimisation']
                print('opt type', opt_type)
                weight = float(target_data['weight'])
                print('weight', weight)

                target = Target(
                    index=index,  
                    name=columns[index] ,  
                    opt_type=opt_type_mapping[opt_type],  
                    weight = weight,
                    experiment_id=expt_info.id  
                )
                
                targets.append(target)

            
            db.session.add_all(targets)
            db.session.commit()
            return redirect(url_for('home_dash.view_experiment', expt_name=expt_info.name)) 

    return render_template(
        "setup_experiment_mo.html",
        user=current_user,
        data_form=data_form,
        hyp_form=hyp_form,
        variable_names=_get_variable_names(),
        num_targets = num_targets

        
    )


@expt_views.route("/add_measurements/<string:expt_name>", methods=["GET", "POST"])
@login_required
def add_measurements(expt_name):
    
    df = [pd.read_json(row.data) for row in Experiment.query.filter_by(name=expt_name).all()][0]
    expt_info = [row for row in Experiment.query.filter_by(name=expt_name).all()][0]
    data_info = Data.query.filter_by(name=expt_info.dataset_name).first()
    variable_list = list(df.columns)
    targets = Target.query.filter_by(experiment_id=expt_info.id).all()
    
    target_column_names=[]
    target_indices=[]
    
    for target in targets:
        target_column_names.append(variable_list[target.index])  
        target_indices.append(int(target.index))
 
    
    print("Targets:", target_column_names)  
    print("Target indices:", target_indices)  

    for col in target_column_names:
        df[col] = df[col].apply(lambda x: f'{x}')

    recs = pd.read_json(expt_info.next_recs)
    print('printing recs',recs)

    if len(recs.columns) < 1:
        recs = pd.DataFrame(columns=df.columns)
        recs.loc[0] = 'insert'

    if "sample-reizman" in expt_info.name:
        emulator_status = True
        df4em = recs
        data = df4em.drop(['yield', 'iteration'], axis=1)
        emulator = get_pretrained_reizman_suzuki_emulator(case=1)
        conditions = DataSet.from_df(data)
        emulator_output = emulator.run_experiments(conditions, rtn_std=True)
        print(emulator_output)
        emulator_value = emulator_output.to_numpy()[0, 5]
        emulator_value_2 = emulator_output.to_numpy()[0, 4]

    else:
        emulator_status = False
        emulator_value = None
        emulator_value_2 = None

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
        target_names=target_column_names,
        recs=recs,
        emulator=emulator_status,
        emulator_value=emulator_value,
        emulator_value_2= emulator_value_2,
    )


@expt_views.route("/run_expt/<string:expt_name>", methods=["GET", "POST"])
@login_required
def run_expt(expt_name):
    expt_info = Experiment.query.filter_by(name=expt_name).first()
    data = pd.read_json(expt_info.data)

    recs = pd.read_json(expt_info.next_recs)
    print('recs:',recs)
    
    targets = Target.query.filter_by(experiment_id=expt_info.id).all()
    
    variable_list = list(data.columns)
    target_column_names=[]
    target_indices=[]

    
    for target in targets:
        target_column_names.append(variable_list[target.index])  
        target_indices.append(int(target.index))

    
    for col in target_column_names:
        data[col] = data[col].apply(lambda x: f'{x}')

    graphs = {}

    for target_name in target_column_names:
        fig = go.Figure([
            go.Scatter(x=data['iteration'], y=data[target_name], mode='markers', name='Experiment(s) run by user'),
            go.Scatter(x=list(recs['iteration']), y=recs[target_name], mode = 'markers', name='Expected outcome of recommended experiment(s)'),
        ])
    
        fig.update_layout(
            xaxis_title="Iteration",
            yaxis_title=f"{target_name.title()}",
            #title=f"{target_name.title()} vs Iteration",
            font=dict(
                family="Courier New, monospace",
                size=18,
                color="RebeccaPurple"
            ),
            autotypenumbers='convert types'
        )

        graphs[target_name] = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


    if request.method == "POST":
        if request.form['action'] == 'add':
            return redirect(url_for("experiment_forms.add_measurements", expt_name=expt_info.name))

    return render_template(
    "run_expt.html", # beneath this is everyting we need to add to html to make it run properly
    user=current_user,
    df=recs,  
    titles=recs.columns.values,  
    graphs = graphs,
    target_names=target_column_names,   
)

#edited function to accommodate multiple targets
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
    #target_name = data['target']
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
