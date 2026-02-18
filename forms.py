from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed
from wtforms import StringField, PasswordField, FloatField, TextAreaField, SelectField, BooleanField, DateField, IntegerField
from wtforms.fields import FileField
from wtforms.validators import (DataRequired, Email, Length, EqualTo,
                                ValidationError, NumberRange, Optional)
import re
from config import Config

class RegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=50)])
    confirm_password = PasswordField('Confirm Password', 
                                    validators=[DataRequired(), EqualTo('password')])
    
    def validate_phone(form, field):
        """Validate phone number format"""
        if not re.match(r'^[0-9+\-\s]+$', field.data):
            raise ValidationError('Invalid phone number format')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')

class FoodForm(FlaskForm):
    name = StringField('Food Name', validators=[DataRequired(), Length(min=2, max=100)])
    category = SelectField('Category', choices=[
        ('pizza', 'Pizza'),
        ('burger', 'Burger'),
        ('sandwich', 'Sandwich'),
        ('south-indian', 'South Indian'),
        ('north-indian', 'North Indian'),
        ('chinese', 'Chinese'),
        ('beverages', 'Beverages'),
        ('desserts', 'Desserts')
    ], validators=[DataRequired()])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0)])
    description = TextAreaField('Description', validators=[DataRequired(), Length(min=10, max=500)])
    image = FileField('Food Image', validators=[FileAllowed(list(Config.ALLOWED_EXTENSIONS), 'Images only!')])
    is_available = BooleanField('Available for ordering', default=True)

class CheckoutForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    location = StringField('Table Number', validators=[DataRequired(), Length(min=1, max=50)])
    payment_method = SelectField('Payment Method', choices=[
        ('room_charge', 'Charge to Table'),
        ('cash', 'Cash'),
        ('card', 'Card Terminal')
    ], validators=[DataRequired()])
    special_instructions = TextAreaField('Special Instructions (Optional)', validators=[Length(max=500)])

class ProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    location = StringField('Table Number', validators=[Optional(), Length(max=50)])

class ServiceRequestForm(FlaskForm):
    service_type = SelectField('Service Type', choices=[
        ('cleaning', 'Clean Table'),
        ('water', 'Water Refill'),
        ('cutlery', 'Extra Cutlery'),
        ('condiments', 'Condiments/Sauces'),
        ('manager', 'Call Manager'),
        ('other', 'Other Request')
    ], validators=[DataRequired()])
    description = TextAreaField('Details / Special Instructions', validators=[Length(max=500)])

class CouponForm(FlaskForm):
    code = StringField('Coupon Code', validators=[DataRequired(), Length(min=3, max=20)])
    discount_type = SelectField('Discount Type', choices=[
        ('percentage', 'Percentage (%)'),
        ('fixed', 'Fixed Amount (₹)')
    ], validators=[DataRequired()])
    value = FloatField('Discount Value', validators=[DataRequired(), NumberRange(min=0)])
    valid_to = DateField('Valid Until', format='%Y-%m-%d', validators=[DataRequired()])
    usage_limit = IntegerField('Usage Limit', default=100, validators=[DataRequired(), NumberRange(min=1)])
    active = BooleanField('Active', default=True)

class AdminUserForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    location = StringField('Table Number', validators=[Optional(), Length(max=50)])
    is_admin = BooleanField('Admin Privileges')