from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

from app.models import ROLE_ADMIN, ROLE_STAFF


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(max=64)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Keep me signed in", default=True)
    submit = SubmitField("Sign in")


class UserForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=64)])
    password = PasswordField("Password", validators=[Optional(), Length(min=6, max=128)])
    role = SelectField("Role", choices=[(ROLE_STAFF, "Staff"), (ROLE_ADMIN, "Admin")])
    submit = SubmitField("Save")
