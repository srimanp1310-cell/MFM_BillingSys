from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Optional, Regexp

from app.models import ROLE_ADMIN, ROLE_STAFF


class RegisterForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=64),
            Regexp(r"^[a-zA-Z0-9_.-]+$", message="Letters, numbers, dots, dashes and underscores only."),
        ],
    )
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=128)])
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Register")


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
