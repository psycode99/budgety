from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expense_tracker.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    budgets = db.relationship('Budget', backref='user', lazy=True)

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    categories = db.relationship('Category', backref='budget', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    budget_id = db.Column(db.Integer, db.ForeignKey('budget.id'), nullable=False)
    expenses = db.relationship('Expense', backref='category', lazy=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    date = db.Column(db.Date, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)

with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists.')
            return redirect(url_for('signup'))
        
        new_user = User(first_name=first_name, last_name=last_name, email=email, password=generate_password_hash(password, method='sha256'))
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully. Please log in.', "success")
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    budgets = Budget.query.filter_by(user_id=current_user.id).all()
    return render_template('budget.html', budgets=budgets)


@app.route('/budget/<int:budget_id>', methods=['GET'])
def get_budget(budget_id):
    budget = Budget.query.get_or_404(budget_id)
    categories = [
        {
            "name": category.name,
            "amount": category.amount,
            "spent": sum(expense.amount for expense in category.expenses),
            "remaining": category.amount - sum(expense.amount for expense in category.expenses)
        }
        for category in budget.categories
    ]
    budget_data = {
        "name": budget.name,
        "total_amount": budget.total_amount,
        "start_date": budget.start_date.strftime("%Y-%m-%d"),
        "end_date": budget.end_date.strftime("%Y-%m-%d"),
        "categories": categories
    }
    return jsonify(budget_data)

@app.route('/create_budget', methods=['GET', 'POST'])
@login_required
def create_budget():
    if request.method == 'POST':
        name = request.form['name'].title()
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        total_amount = float(request.form['total_amount'])
        
       
        category_names = request.form.getlist('category_name[]')
        category_amounts = request.form.getlist('category_amount[]')
        amt = 0

        for name, amount in zip(category_names, category_amounts):
            amount = int(amount)
            amt += amount

        if amt > total_amount:
            flash("Category amounts are greater than set budget total amount", "error")
            return redirect(url_for('dashboard'))
        
        new_budget = Budget(name=name, start_date=start_date, end_date=end_date, total_amount=total_amount, user_id=current_user.id)
        db.session.add(new_budget)
        db.session.commit()
        
        for name, amount in zip(category_names, category_amounts):
            new_category = Category(name=name.title(), amount=float(amount), budget_id=new_budget.id)
            db.session.add(new_category)
        
        db.session.commit()
        flash('Budget created successfully.', "success")
        return redirect(url_for('dashboard'))
    
    return render_template('budget.html')

@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        amount = float(request.form['amount'])
        description = request.form['description'].title()
        category_id = int(request.form['category'])
        budget_id = int(request.form['budget'])
        date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()


        check_cat = Category.query.filter_by(id=category_id, budget_id=budget_id).first()
        if not check_cat:
            flash("Category is not associated with the choosen budget", "error")
            return redirect(url_for('add_expense'))
        
        new_expense = Expense(amount=amount, description=description, date=date, category_id=category_id)
        db.session.add(new_expense)
        db.session.commit()
        
        flash('Expense added successfully.', "success")
        return redirect(url_for('add_expense'))
    
    categories = Category.query.join(Budget).filter(Budget.user_id == current_user.id).all()
    budgets = Budget.query.filter_by(user_id=current_user.id).all()
    expenses = Expense.query.join(Category).join(Budget).filter(Budget.user_id == current_user.id).all()

    return render_template('add_expense.html', categories=categories, budgets=budgets, expenses=expenses)

@app.route('/get_budget_details/<int:budget_id>')
@login_required
def get_budget_details(budget_id):
    budget = Budget.query.get_or_404(budget_id)
    if budget.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    categories = []
    for category in budget.categories:
        total_expenses = sum(expense.amount for expense in category.expenses)
        remaining = category.amount - total_expenses
        categories.append({
            'name': category.name,
            'amount': category.amount,
            'spent': total_expenses,
            'remaining': remaining
        })
    
    return jsonify({
        'id': budget.id,
        'name': budget.name,
        'start_date': budget.start_date.strftime('%Y-%m-%d'),
        'end_date': budget.end_date.strftime('%Y-%m-%d'),
        'total_amount': budget.total_amount,
        'categories': categories
    })

if __name__ == '__main__':
    app.run(debug=True)