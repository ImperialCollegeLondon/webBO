from . import db 
from flask_login import UserMixin
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB

class Data(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True)
    data = db.Column(db.Text)
    variables = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

class Target(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    index = db.Column(db.Integer, nullable=False)  
    name = db.Column(db.String(255), nullable=False) 
    opt_type = db.Column(db.String(10), nullable=False)  # "MAX" or "MIN"
    weight = db.Column(db.Float, nullable=False)  
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiment.id'), nullable=False)
    experiment = db.relationship('Experiment', backref=db.backref('targets', lazy=True, cascade="all, delete-orphan"))


class Experiment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True)
    dataset_name = db.Column(db.String(150))
    data = db.Column(db.Text)
    objective = db.Column(db.String(150), nullable = False) # will contain 'MULTI' or 'SINGLE'
    fidelity = db.Column(db.String(150), nullable = False) # will contain 'MULTI' or 'SINGLE'
    n_targets = db.Column(db.Integer, nullable = False)
    variables = db.Column(db.Text)
    kernel = db.Column(db.String(150))
    acqFunc = db.Column(db.String(150))
    batch_size = db.Column(db.Integer)
    next_recs = db.Column(db.Text)
    iterations_completed = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    datas = db.relationship("Data")
    expts = db.relationship("Experiment")
