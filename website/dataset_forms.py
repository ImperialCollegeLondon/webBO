from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, session
from flask_login import login_required, current_user
# from .models import Data, Experiment
from . import db 
import json
import pandas as pd
from werkzeug.utils import secure_filename
# from . import bo_integration


data_views = Blueprint("dataset_forms", __name__)


@data_views.route("/", methods=["GET", "POST"])
@login_required
def home():
    if request.method == "POST":
        pass
    return render_template("dataset_form.html", user=current_user)