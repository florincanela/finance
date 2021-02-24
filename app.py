import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from re import fullmatch
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():

    rows = db.execute('SELECT * FROM shares WHERE user_id = ?',session['user_id'])
    cash = db.execute('SELECT cash FROM users WHERE id = ?', session['user_id'])
    db.execute('DELETE FROM shares WHERE user_id = ? AND shares = 0',session['user_id'])

    total = 0

    for row in rows:
        x = lookup(row['symbol'])
        total += float(x['price']) * float(row['shares'])
    total += float(cash[0]['cash'])


    return render_template('index.html', cash=cash[0]['cash'], rows=rows, lookup=lookup, total = total)






@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == 'POST':
        if not request.form.get('symbol'):
            flash('Please provide symbol.', "dark")
            return redirect(request.url)

        if not request.form.get('shares'):
            flash('Please provide number of shares.', "dark")
            return redirect(request.url)

        if not request.form.get('shares').isnumeric():
            flash('Invalid amount of shares', "warning")
            return redirect(request.url)

        if float(request.form.get('shares')) < 1 or float(request.form.get('shares')) % 1 != 0 :
            flash('Invalid amount of shares', "warning")
            return redirect(request.url)

        x = lookup(request.form.get('symbol'))

        if x is None:
            flash('Symbol not found', "dark")
            return redirect(request.url)

        user_cash = db.execute('SELECT cash FROM users WHERE id = ?', session['user_id'])
        shares_costs = int(x['price'] *int(request.form.get('shares')))
        if user_cash[0]['cash'] - shares_costs < 0:
            flash('Insuficient Funds', "warning")
            return redirect(request.url)
        else:

            rows = db.execute("SELECT symbol,shares FROM shares WHERE user_id =?", session['user_id'])
            c = True;
            for row in rows:
                if row['symbol'] == x['symbol']:
                    db.execute('UPDATE shares SET shares = ? WHERE user_id = ? AND symbol = ?', int(request.form.get('shares')) +int(row['shares']) , session['user_id'], x['symbol'])
                    c = False;
                    break

            if c:
                db.execute('INSERT INTO shares (symbol,shares,user_id) VALUES(?,?,?)',
                x['symbol'], request.form.get('shares'), session['user_id'])

            #updating history
            db.execute('INSERT INTO history (symbol,shares,price,user_id,ts) VALUES(?,?,?,?,?)',
                x['symbol'], request.form.get('shares'), x['price'], session['user_id'], datetime.now())

            db.execute('UPDATE users SET cash = ? WHERE id = ?',user_cash[0]['cash'] - shares_costs, session['user_id'])

            return redirect('/')



    return render_template('buy.html')


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    rows = db.execute('SELECT * FROM history WHERE user_id = ?', session['user_id'])


    return render_template('history.html', rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            flash("Please enter a valid username", "danger")
            return render_template("login.html")

        # Ensure password was submitted
        elif not request.form.get("password"):
            flash("Please enter password", "danger")
            return render_template("login.html")


        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            flash("Invalid username and/or password", "danger")
            return render_template("login.html")


        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        flash("Logged In succesfully!", "success")
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get('symbol'):
            flash('Please provide symbol', "warning")
            return render_template('quote.html')

        else:
            x = lookup(request.form.get('symbol'))

            if x is not None:

                return render_template('quoted.html', company= x['name'], symbol= x['symbol'], price= x['price'])

            else:
                flash('Symbol not found', "dark")
                return render_template('quote.html')

    else:
        return render_template('quote.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get('username'):
            flash('Please enter username.', "warning")
            return render_template('register.html')

        elif not request.form.get('password'):
            flash('Please provide password', "warning")
            return render_template('register.html')

        if not fullmatch(r"[A-Za-z0-9@#$%^&+=]{8,}", request.form.get('password') ):
            flash('Password requiers Minimum eight characters, at least one letter and one number:', "warning")
            return render_template('register.html')

        elif not request.form.get('confirmation'):
            flash('Please confirm your password', "warning")
            return render_template('register.html')

        rows = db.execute('SELECT username,id FROM users WHERE username = ?', request.form.get('username'))

        if len(rows) != 0:
            flash("username already in use", "danger")
            return render_template('register.html')

        elif request.form.get('password') != request.form.get('confirmation'):
            flash("passwords don't match", "danger")
            return render_template('register.html')



        else:
            db.execute('INSERT INTO users (username,hash) VALUES(?, ?)', request.form.get('username'), generate_password_hash(request.form.get('password')))
            rows = db.execute('SELECT id FROM users WHERE username = ?', request.form.get('username'))
            session['user_id'] = rows[0]['id']
            flash("Registered Succesfully!", 'success')
            return redirect('/')
    else:
        return render_template('register.html')


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    """Sell shares of stock"""
    rows = db.execute('SELECT * FROM shares WHERE user_id = ?', session['user_id'])

    if request.method == 'POST':
        if not request.form.get("symbol"):
            flash("Please provide symbol", "warning")
            return render_template('sell.html')

        if not request.form.get("shares") or int(request.form.get("shares")) < 1:
            flash("Invalid number of shares", "warning")
            return render_template('sell.html')


        for row in rows:
            if row['symbol'] == request.form.get('symbol'):
                if int(row['shares']) < int(request.form.get('shares')):
                    flash('Not enough shares in your Portfolio', "warning")
                    return render_template('sell.html')

                x = int(row['shares']) - int(request.form.get('shares'))
                db.execute('UPDATE shares SET shares = ? WHERE user_id = ? AND symbol = ?',x , session['user_id'], request.form.get('symbol') )
                y = lookup(row['symbol'])
                break

            flash('Invalid Symbol', "danger")
            return render_template('sell.html')


        user_cash = db.execute('SELECT cash FROM users WHERE id = ?', session['user_id'])
        shares_costs = int(y['price']) * int(request.form.get('shares'))
        db.execute('INSERT INTO history (symbol,shares,price,user_id,ts) VALUES(?,?,?,?,?)',
        y['symbol'], int(request.form.get('shares'))* -1, y['price'], session['user_id'], datetime.now())
        db.execute('UPDATE users SET cash = ? WHERE id = ?',user_cash[0]['cash'] + shares_costs, session['user_id'])

        return redirect('/')


    return render_template('sell.html', rows = rows)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    flash(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
