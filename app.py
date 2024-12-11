from flask import Flask, render_template, request, redirect, url_for, flash, blueprints, session
from sqlalchemy import inspect, text
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash

#import other blueprints
from leaser import leaser_blueprint
from renter import renter_blueprint

app = Flask(__name__)
#configure database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///C:/Users/13145/Desktop/Airbnb For Cars CS348 project/airbnb_cars.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'
db.init_app(app)
with app.app_context():
        from models import User, Car, Booking, Location, Availability


app.register_blueprint(leaser_blueprint)
app.register_blueprint(renter_blueprint)



@app.route('/')

def home():
    greeting = "Welcome to Airbnb for Cars"
    return render_template('index.html', greeting = greeting)

def create_tables_if_not_exists():
    #creates all tables and calls the create indexes
    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        required_tables = {'user', 'car', 'booking', 'location', 'availability'}
        if not required_tables.issubset(tables):
            db.create_all()
            db.session.commit()
            inspector = inspect(db.engine)
            create_indexes()
        else:
            print("Tables already exist:", tables)
            create_indexes()


def create_indexes():
    #Creates indexes of queries that will be used a lot
    index_on_price_filter = text("CREATE INDEX IF NOT EXISTS index_car_price_per_day ON car(price_per_day)")
    db.session.execute(index_on_price_filter)

    index_on_city_filter = text("CREATE INDEX IF NOT EXISTS index_location_city ON location(city)")
    db.session.execute(index_on_city_filter)

    index_make_of_car = text("CREATE INDEX IF NOT EXISTS index_car_make ON car(make)")
    db.session.execute(index_make_of_car)

    index_availability = text("CREATE INDEX IF NOT EXISTS index_car_availability ON availability(car_id, available_from, available_to)")
    db.session.execute(index_availability)

    booking_index_on_car_id = text("CREATE INDEX IF NOT EXISTS index_booking_car_id ON booking(car_id)")
    db.session.execute(booking_index_on_car_id)

    booking_index_on_renter_id = text("CREATE INDEX IF NOT EXISTS index_booking_renter_id ON booking(renter_id)")
    db.session.execute(booking_index_on_renter_id)

    db.session.commit()
    


@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
     #creates a new account
     if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        password = request.form.get('password')
        phone_number = request.form.get('phone_number')
        role = request.form.get('role')
        #creates new user
        if not all([full_name,email,password,phone_number,role]):
            flash("All fields are required")
            return redirect(url_for('create_account'))
        #check to see if account already created
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered')
            return redirect(url_for('create_account'))
        password_hash = generate_password_hash(password)
        new_user = User(name = full_name, email =email, password_hash = password_hash, phone_number=phone_number, role = role)
        db.session.add(new_user)
        db.session.commit()
        flash('Account was created Successfully!')
        return redirect(url_for('login'))
     return render_template('create_account.html')


@app.route('/leaser_home')
def leaser_home():
    leaser_greeting = "Welcome to the home page of the leaser!"

    leaser_id = session.get('user_id')
    if not leaser_id:
        flash("Log In")
        return redirect(url_for('login'))
    #find all cars owned by the leaser
    sql_query = text("SELECT * FROM car WHERE owner_id = :leaser_id ORDER BY price_per_day")
    result = db.session.execute(sql_query, {"leaser_id": leaser_id}).fetchall()
    cars = [dict(row._mapping) for row in result]

    return render_template('leaser_home.html', leaser_greeting = leaser_greeting, cars = cars)

@app.route('/renter_home')
def renter_home():
    renter_greeting = "Welcome to the home page of the renter!"

    renter_id = session.get('user_id')
    if not renter_id:
        flash("Log In")
        return redirect(url_for('login'))
    
    #filter paramaters
    min_price = request.args.get('min_price', type = float)
    max_price = request.args.get('max_price', type = float)
    make = request.args.get('make')
    city = request.args.get('city')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    #get all cars
    all_cars_query = text("""SELECT car.car_id FROM car JOIN location
                          ON car.location_id = location.location_id""")
    all_cars_results = db.session.execute(all_cars_query).fetchall()
    current_car_ids = {row.car_id for row in all_cars_results}
    
    if min_price is not None:
        min_price_query = text("""SELECT car_id FROM car WHERE price_per_day >= :min_price""")
        min_price_result = db.session.execute(min_price_query,{"min_price": min_price}).fetchall()
        min_price_ids = {row.car_id for row in min_price_result}
        current_car_ids = current_car_ids.intersection(min_price_ids)


    if max_price is not None:
        max_price_query = text("""SELECT car_id FROM car WHERE price_per_day <= :max_price""")
        max_price_result = db.session.execute(max_price_query,{"max_price": max_price}).fetchall()
        max_price_ids = {row.car_id for row in max_price_result}
        current_car_ids = current_car_ids.intersection(max_price_ids)

    if make:
        make_query = text("""SELECT car_id FROM car WHERE make = :make""")
        make_result = db.session.execute(make_query, {"make": make}).fetchall()
        make_ids = {row.car_id for row in make_result}
        current_car_ids = current_car_ids.intersection(make_ids)

    if city:
        city_query = text("""SELECT car.car_id FROM car JOIN location on car.location_id = location.location_id
        WHERE location.city = :city""")
        city_result = db.session.execute(city_query, {"city":city}).fetchall()
        city_ids = {row.car_id for row in city_result}
        current_car_ids = current_car_ids.intersection(city_ids)

    if start_date and end_date:
        availability_query = text("""SELECT car_id FROM availability
        WHERE available_from <= :start_date and available_to >= :end_date""")
        availability_result = db.session.execute(availability_query, {"start_date": start_date, "end_date": end_date}).fetchall()
        availability_ids = {row.car_id for row in availability_result}
        current_car_ids = current_car_ids.intersection(availability_ids)

    if not current_car_ids:
        cars = []
    else:
        final_get_all = text(f"""SELECT car.car_id as car_id, car.make AS make, car.model AS model, car.year as year, car.price_per_day AS price_per_day,
        location.address AS address, location.city AS city, location.state AS state, location.zip_code AS zip_code, location.country AS country
        FROM car
        JOIN location ON car.location_id = location.location_id
        WHERE car.car_id IN ({",".join(str(cid) for cid in current_car_ids)})""")
        final_result = db.session.execute(final_get_all).fetchall()
        cars = [dict(row._mapping) for row in final_result]


    return render_template('renter_home.html', renter_greeting = renter_greeting, cars = cars)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password) and user.role == role:
            session['user_id'] = user.user_id
            session['role'] = user.role
            flash("Login Successful")
            if user.role == "leaser":
                return redirect(url_for('leaser_home'))
            else:
                return redirect(url_for('renter_home'))
        else:
            flash("Ivalid Email or Password")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))




if __name__ == '__main__':
    create_tables_if_not_exists()
    app.run(debug=True)
