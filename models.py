from extensions import db

class User(db.Model):
    __tablename__ = 'user'
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    phone_number = db.Column(db.String(15), nullable = False)
    role = db.Column(db.String(10), nullable=False)  # 'renter' or 'leaser'

class Location(db.Model):
    __tablename__ = 'location'

    location_id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable = False)
    state = db.Column(db.String(100), nullable = False)
    zip_code = db.Column(db.String(10), nullable = False)
    country = db.Column(db.String(100), nullable = False)

class Car(db.Model):
    __tablename__ = 'car'

    car_id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    make = db.Column(db.String(50), nullable=False)
    model = db.Column(db.String(51), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('location.location_id'), nullable=False)
    price_per_day = db.Column(db.Numeric(10,2), nullable = False)

class Availability(db.Model):
    __tablename__ = 'availability'

    availability_id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('car.car_id'), nullable=False)
    available_from = db.Column(db.Date, nullable=False)
    available_to = db.Column(db.Date, nullable=False)

class Booking(db.Model):
    __tablename__ = 'booking'

    booking_id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey('car.car_id'), nullable=False)
    renter_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    booking_start = db.Column(db.Date, nullable=False)
    booking_end = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), nullable=False)  # 'confirmed', 'pending', 'cancelled', 'completed'
    total_price = db.Column(db.Numeric(10,2), nullable = False)
    booking_created = db.Column(db.Date, nullable = False, default = db.func.now())
