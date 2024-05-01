from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, session
from flask_login import login_required, current_user
from .models import Data #, Experiment
from . import db 
import json
import pandas as pd
from werkzeug.utils import secure_filename
# from . import bo_integration


data_views = Blueprint("dataset_forms", __name__)


@data_views.route("/select-method", methods=["GET", "POST"])
@login_required
def select_upload_method():
    if request.method == "POST":
        if request.form['action'] == "csv":
            return redirect(url_for("dataset_forms.upload"))
        elif request.form['action'] == "datalab":
            return redirect(url_for("dataset_forms.connect"))
    return render_template("select_dataset_upload_method.html", user=current_user)


@data_views.route("/connect", methods=["GET", "POST"])
@login_required
def connect():
    if request.method == "POST":
        if request.form['action'] == "submit":
            # check the dataset name
            name = request.form.get('dataName')
            if db.session.query(Data.id).filter_by(name=name).scalar() is not None:
                flash("Dataset names must be unique.", category="error")

            
    return render_template("connect_datalab.html", user=current_user)


@data_views.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        datafile = request.files["formFile"]
        if datafile:
            filename = secure_filename(datafile.filename)
            datafile.save(filename)
            df = pd.read_csv(filename)
            variable_df = pd.DataFrame(df.columns, columns=["variables"])
            name = request.form.get('dataName')
            if db.session.query(Data.id).filter_by(name=name).scalar() is not None:
                flash("Dataset names must be unique.", category="error")
            else:
                input_data = Data(
                    name=f"{name}",
                    data=df.to_json(orient='records'),
                    variables=variable_df.to_json(orient='records'),
                    user_id=current_user.id
                )
                db.session.add(input_data)
                db.session.flush()
                db.session.commit()
                # session["dataID"] = input_data.id
                flash("Upload successful!", category="success")
                return redirect(url_for("home_dash.home"))
        else:
            flash("Upload unsuccessful. Try again.", category="error")
    return render_template("upload.html", user=current_user)
