from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

NEW_SENTINEL = -1  # select value meaning "create a new category/brand"


class CategoryForm(FlaskForm):
    name = StringField("Category name", validators=[DataRequired(), Length(max=64)])
    track_size = BooleanField("Products in this category have a size (e.g. mattresses)")
    submit = SubmitField("Add category")


class BrandForm(FlaskForm):
    name = StringField("Brand name", validators=[DataRequired(), Length(max=64)])
    category_id = SelectField("Category", coerce=int)
    submit = SubmitField("Add brand")


class ProductForm(FlaskForm):
    name = StringField("Product name", validators=[DataRequired(), Length(max=128)])
    code = StringField("Code / SKU", validators=[Optional(), Length(max=32)],
                       description="Leave blank to auto-generate.")
    category_id = SelectField("Category", coerce=int)
    new_category_name = StringField("New category name", validators=[Optional(), Length(max=64)])
    new_category_track_size = BooleanField("New category has sizes")
    brand_id = SelectField("Brand", coerce=int)
    new_brand_name = StringField("New brand name", validators=[Optional(), Length(max=64)])
    size = StringField("Size", validators=[Optional(), Length(max=64)])
    unit = SelectField("Unit", choices=[("piece", "piece"), ("set", "set")], default="piece")
    unit_price = DecimalField("Selling price", places=2, validators=[DataRequired(), NumberRange(min=0)])
    cost_price = DecimalField("Cost price", places=2, validators=[Optional(), NumberRange(min=0)])
    reorder_level = IntegerField("Reorder level (low-stock alert)", validators=[Optional(), NumberRange(min=0)],
                                 description="Alert when quantity on hand falls to this level. Leave blank for no alert.")
    description = TextAreaField("Description", validators=[Optional()])
    submit = SubmitField("Save product")

    def set_choices(self):
        from app.models import Brand, Category

        cats = Category.query.filter_by(is_active=True).order_by(Category.name).all()
        self.category_id.choices = [(c.id, c.name) for c in cats] + [(NEW_SENTINEL, "➕ New category…")]
        brands = Brand.query.filter_by(is_active=True).order_by(Brand.name).all()
        self.brand_id.choices = (
            [(0, "— no brand —")]
            + [(b.id, f"{b.name}") for b in brands]
            + [(NEW_SENTINEL, "➕ New brand…")]
        )
        # data map used by JS to filter brands per category / toggle size field
        self.category_meta = {c.id: {"track_size": c.track_size} for c in cats}
        self.brand_meta = {b.id: {"category_id": b.category_id} for b in brands}
