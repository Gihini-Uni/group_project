from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from collections import defaultdict
from db import db
from sqlalchemy import func, extract, cast, Date
from calendar import week
from flask_login import LoginManager
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from flask_migrate import Migrate


app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expense_tracker.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)
# Create DB tables (only run once or on startup)
with app.app_context():
    db.create_all()


from models import User, Income, Expense, IncomeCategory, ExpenseCategory


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
  return User.query.get(int(user_id))

# Report route
@app.route('/report')
@login_required
def report():
    user_id = current_user.id
    currency = current_user.currency if current_user.currency else "USD"


    incomes = Income.query.filter_by(user_id=user_id).order_by(Income.date.asc()).all()
    expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.date.asc()).all()

    total_income = sum(i.amount for i in incomes)
    total_expense = sum(e.amount for e in expenses)
    savings = total_income - total_expense

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    income_category_filter = request.args.get('income_category')
    expense_category_filter = request.args.get('expense_category')

    income_query = Income.query.filter_by(user_id=user_id)
    expense_query = Expense.query.filter_by(user_id=user_id)

    if start_date:
        income_query = income_query.filter(Income.date >= start_date)
        expense_query = expense_query.filter(Expense.date >= start_date)
    if end_date:
        income_query = income_query.filter(Income.date <= end_date)
        expense_query = expense_query.filter(Expense.date <= end_date)

    if income_category_filter and income_category_filter != 'All':
        income_query = income_query.filter(Income.category == income_category_filter)

    if expense_category_filter and expense_category_filter != 'All':
        expense_query = expense_query.filter(Expense.category == expense_category_filter)

    filtered_incomes = income_query.order_by(Income.date.asc()).all()
    filtered_expenses = expense_query.order_by(Expense.date.asc()).all()

    filtered_income_total = sum(i.amount for i in filtered_incomes)
    filtered_expense_total = sum(e.amount for e in filtered_expenses)
    filtered_savings_total = filtered_income_total - filtered_expense_total

    income_transactions = []
    expense_transactions = []
    
    for income in filtered_incomes:
        income_transactions.append({
            'date': income.date.strftime('%Y-%m-%d'),
            'category': income.category,
            'amount': income.amount
        })
    for expense in filtered_expenses:
        expense_transactions.append({
            'date': expense.date.strftime('%Y-%m-%d'),
            'category': expense.category,
            'amount': expense.amount
        })

    income_transactions.sort(key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'))
    expense_transactions.sort(key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'))

    group_by = request.args.get('group_by', 'monthly')  # default to 'monthly'

    def prepare_grouped_data(records, group_by='monthly'):
        grouped_totals = defaultdict(float)
        for r in records:
            if group_by == 'daily':
                key = r.date.strftime('%Y-%m-%d')
            elif group_by == 'weekly':
                key = f"{r.date.strftime('%Y')}-W{r.date.isocalendar()[1]}"
            else:  # monthly
                key = r.date.strftime('%Y-%m')
            grouped_totals[key] += r.amount
        return grouped_totals

    income_grouped = prepare_grouped_data(filtered_incomes, group_by)
    expense_grouped = prepare_grouped_data(filtered_expenses, group_by)
    periods = sorted(set(list(income_grouped.keys()) + list(expense_grouped.keys())))

    income_values = [income_grouped.get(p, 0) for p in periods]
    expense_values = [expense_grouped.get(p, 0) for p in periods]
    savings_values = [income_grouped.get(p, 0) - expense_grouped.get(p, 0) for p in periods]

    def prepare_category_data(records):
        category_totals = defaultdict(float)
        for r in records:
            category_totals[r.category] += r.amount
        return category_totals

    income_category_data = prepare_category_data(filtered_incomes)
    expense_category_data = prepare_category_data(filtered_expenses)

    income_categories = list(income_category_data.keys())
    income_category_values = list(income_category_data.values())

    expense_categories = list(expense_category_data.keys())
    expense_category_values = list(expense_category_data.values())

    # Fetch all distinct categories (for dropdown filters)
    all_income_categories = [c[0] for c in db.session.query(Income.category).filter_by(user_id=user_id).distinct()]
    all_expense_categories = [c[0] for c in db.session.query(Expense.category).filter_by(user_id=user_id).distinct()]

    from calendar import monthrange

    # Get current and previous month
    today = datetime.today()
    current_year = today.year
    current_month = today.month
    previous_month = current_month - 1 if current_month > 1 else 12
    previous_month_year = current_year if current_month > 1 else current_year - 1

    # Filter this year's records
    year_incomes = [i for i in incomes if i.date.year == current_year]
    year_expenses = [e for e in expenses if e.date.year == current_year]

    # Filter for current and previous month
    def is_month(record, y, m):
        return record.date.year == y and record.date.month == m

    current_month_income = sum(i.amount for i in incomes if is_month(i, current_year, current_month))
    current_month_expense = sum(e.amount for e in expenses if is_month(e, current_year, current_month))
    current_month_savings = current_month_income - current_month_expense

    previous_month_income = sum(i.amount for i in incomes if is_month(i, previous_month_year, previous_month))
    previous_month_expense = sum(e.amount for e in expenses if is_month(e, previous_month_year, previous_month))
    previous_month_savings = previous_month_income - previous_month_expense

    # Calculate savings increase
    savings_increase = current_month_savings - previous_month_savings

    # Average income and expense for current year
    avg_income = sum(i.amount for i in year_incomes) / len(
        set((i.date.month for i in year_incomes))) if year_incomes else 0
    avg_expense = sum(e.amount for e in year_expenses) / len(
        set((e.date.month for e in year_expenses))) if year_expenses else 0

    # Most spending category (current year)
    from collections import Counter

    def top_category(records):
        c = Counter()
        for r in records:
            if r.date.year == current_year:
                c[r.category] += r.amount
        return c.most_common(1)[0][0] if c else 'N/A'

    top_spending_category = top_category(expenses)
    top_earning_category = top_category(incomes)

    return render_template('report.html',
                           total_income=total_income,
                           total_expense=total_expense,
                           savings=savings,
                           filtered_income_total=filtered_income_total,
                           filtered_expense_total=filtered_expense_total,
                           filtered_savings_total=filtered_savings_total,
                           income_transactions=income_transactions,
                           expense_transactions=expense_transactions,
                           periods=periods,
                           income_values=income_values,
                           expense_values=expense_values,
                           savings_values=savings_values,
                           income_categories=income_categories,
                           income_category_values=income_category_values,
                           expense_categories=expense_categories,
                           expense_category_values=expense_category_values,
                           all_income_categories=all_income_categories,
                           all_expense_categories=all_expense_categories,
                           selected_income_category=income_category_filter if income_category_filter else 'All',
                           selected_expense_category=expense_category_filter if expense_category_filter else 'All',
                           savings_increase=savings_increase,
                           avg_income=avg_income,
                           avg_expense=avg_expense,
                           top_spending_category=top_spending_category,
                           top_earning_category=top_earning_category,
                           group_by=group_by,
                           currency=currency,

                           )

@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        currency = request.form['currency']  # NEW: get selected currency

        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register'))

        user = User(username=username, password=password, currency=currency)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))  # Make sure this route exists
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You’ve been logged out.")
    return redirect(url_for('login'))

#from sqlalchemy import func

@app.route('/dashboard')
@login_required
def dashboard():
    # Get current user from session
    #user_id = session.get('current_user')
    user_id = current_user.id
    if not user_id:
        flash('Please log in to continue.')
        return redirect(url_for('login'))

    user = User.query.get(user_id)
    if not user:
        flash('User not found.')
        return redirect(url_for('login'))

    # Totals
    total_income = db.session.query(func.sum(Income.amount))\
        .filter_by(user_id=user_id).scalar() or 0
    total_expense = db.session.query(func.sum(Expense.amount))\
        .filter_by(user_id=user_id).scalar() or 0
    balance = total_income - total_expense

    # Income by Category
    income_by_category = db.session.query(
        Income.category,
        func.sum(Income.amount).label('total_amount')
    ).filter_by(user_id=user_id)\
     .group_by(Income.category).all()
    income = [{'category': i[0], 'total_amount': float(i[1])} for i in income_by_category]

    # Expense by Category
    expense_by_category = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label('total_amount')
    ).filter_by(user_id=user_id)\
     .group_by(Expense.category).all()
    expense = [{'category': e[0], 'total_amount': float(e[1])} for e in expense_by_category]

    # Monthly Income
    income_monthly_data = db.session.query(
        func.strftime('%Y-%m', Income.date).label('month'),
        func.sum(Income.amount).label('amount')
    ).filter_by(user_id=user_id)\
     .group_by('month')\
     .order_by('month').all()
    income_monthly = [{'month': m[0], 'amount': float(m[1])} for m in income_monthly_data]

    # Monthly Expense
    expense_monthly_data = db.session.query(
        func.strftime('%Y-%m', Expense.date).label('month'),
        func.sum(Expense.amount).label('amount')
    ).filter_by(user_id=user_id)\
     .group_by('month')\
     .order_by('month').all()
    expense_monthly = [{'month': m[0], 'amount': float(m[1])} for m in expense_monthly_data]

    return render_template(
        'dashboard.html',
        income_total=total_income,
        expense_total=total_expense,
        balance=balance,
        income=income,
        expense=expense,
        income_monthly=income_monthly,
        expense_monthly=expense_monthly,
        currency=user.currency  # <-- This line ensures correct currency is shown
    )
    
@app.route('/add_income', methods=['GET', 'POST'])
def add_income():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        amount = float(request.form['amount'])
        category = request.form['category']
        new_income = Income(amount=amount, category=category,
                            user_id=session['user_id'], date=datetime.now())
        db.session.add(new_income)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('income.html')

@app.route('/delete_income/<int:id>')
def delete_income(id):
    income = Income.query.get_or_404(id)
    db.session.delete(income)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/add_expense', methods=['GET', 'POST'])
def add_expense():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        amount = float(request.form['amount'])
        category = request.form['category']
        new_expense = Expense(amount=amount, category=category,
                              user_id=session['user_id'], date=datetime.now())
        db.session.add(new_expense)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return render_template('expense.html')

@app.route('/delete_expense/<int:id>')
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    db.session.delete(expense)
    db.session.commit()
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists('expense_tracker.db'):
            db.create_all()
    app.run(debug=True)

