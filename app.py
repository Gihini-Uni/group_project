from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
#from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from collections import defaultdict
from db import db

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expense_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

from models import User, Income, Expense

#login_manager = LoginManager()
#login_manager.init_app(app)
#login_manager.login_view = 'login'

#@login_manager.user_loader
#def load_user(user_id):
    #return User.query.get(int(user_id))

# Report route
@app.route('/report')
def report():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Get data from DB
    incomes = Income.query.filter_by(user_id=user_id).all()
    expenses = Expense.query.filter_by(user_id=user_id).all()

    # Calculate totals
    total_income = sum(i.amount for i in incomes)
    total_expense = sum(e.amount for e in expenses)
    savings = total_income - total_expense

    def prepare_chart_data(records, kind='income'):
        category_totals = defaultdict(float)
        daily_totals = defaultdict(float)

        for record in records:
            category_totals[record.category] += record.amount
            date_str = record.date.strftime('%Y-%m-%d')
            daily_totals[date_str] += record.amount

        return {
            'categories': list(category_totals.keys()),
            'category_values': list(category_totals.values()),
            'dates': list(daily_totals.keys()),
            'values': list(daily_totals.values())
        }

    # Prepare report data for all 3 types
    report_data = {
        'income': prepare_chart_data(incomes, 'income'),
        'expense': prepare_chart_data(expenses, 'expense'),
        'savings': {
            'categories': ['Savings'],
            'category_values': [savings],
            'dates': sorted(set([i.date.strftime('%Y-%m-%d') for i in incomes] + [e.date.strftime('%Y-%m-%d') for e in expenses])),
            'values': []
        }
    }

    # For savings by date: (income - expense) per date
    income_by_date = defaultdict(float)
    expense_by_date = defaultdict(float)
    for i in incomes:
        date_str = i.date.strftime('%Y-%m-%d')
        income_by_date[date_str] += i.amount
    for e in expenses:
        date_str = e.date.strftime('%Y-%m-%d')
        expense_by_date[date_str] += e.amount

    all_dates = sorted(set(list(income_by_date.keys()) + list(expense_by_date.keys())))
    savings_by_date = []
    for date in all_dates:
        savings_by_date.append(income_by_date[date] - expense_by_date[date])

    report_data['savings']['values'] = savings_by_date

    return render_template(
        'report.html',
        total_income=total_income,
        total_expense=total_expense,
        savings=savings,
        report_data=report_data
    )
