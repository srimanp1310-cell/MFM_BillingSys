from flask_wtf import FlaskForm
from wtforms import DateField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional


class PurchaseHeaderForm(FlaskForm):
    supplier_name = StringField("Supplier name", validators=[DataRequired(), Length(max=128)])
    supplier_invoice_number = StringField(
        "Supplier invoice no.", validators=[DataRequired(), Length(max=64)]
    )
    purchase_date = DateField("Stock arrival date", validators=[DataRequired()])
    note = TextAreaField("Note", validators=[Optional()])
    submit = SubmitField("Save stock entry")
