from . import db 
from flask_login import UserMixin
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    datas = db.relationship("Data")
    expts = db.relationship("Experiment")


class Data(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True)
    data = db.Column(db.Text)
    variables = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))


class Experiment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True)
    dataset_name = db.Column(db.String(150))
    data = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
