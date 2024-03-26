from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from . import db 
import json
from .models import Data, Experiment


home_dash = Blueprint("home_dash", __name__)


@home_dash.route("/", methods=["GET", "POST"])
@login_required
def home():
    if request.method == "POST":
        if request.form['action'] == "add-dataset":
            return redirect(url_for("dataset_forms.upload"))
        elif request.form['action'] == "add-experiment":
            return redirect(url_for("experiment_forms.setup"))
        else:
            print(request.form['action'])
            print('working?')

    return render_template("home.html", user=current_user)


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
