from time import strftime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import Car, Availability, Booking, User, Location
from extensions import db
from sqlalchemy import update, text, or_, and_, func
from datetime import datetime, timedelta
from sqlalchemy.sql import func
import sqlite3


renter_blueprint = Blueprint('renter', __name__, url_prefix='/renter')

@renter_blueprint.route('/book_car/<int:car_id>', methods= ['GET', 'POST'])
def book_car(car_id):
    if 'user_id' not in session or session.get('role') != 'renter':
        flash("You need to be logged in")
        return redirect(url_for('login'))
   # car_id = request.args.get('car_id', type=int)
    
    if not car_id:
        flash("No car selected")
        return redirect(url_for('renter_home'))
    #get car and location
    car = db.session.query(Car, Location).join(Location).filter(Car.car_id == car_id).first()
    
    if not car: 
        flash("car not found")
        return redirect(url_for('renter_home'))
    car, location = car
    #get availability and bookings
    availabilities = db.session.query(Availability).filter_by(car_id=car_id).all()
    confirmed_bookings = db.session.query(Booking).filter(Booking.car_id == car_id, Booking.status == 'confirmed').all()
    #find dates that are unavailable
    unavailable_dates = set()
    today = datetime.today().date()
    end_date = today + timedelta(days=365)
    date_cursor = today
    while date_cursor <= end_date:
        unavailable_dates.add(date_cursor.strftime('%Y-%m-%d'))
        date_cursor += timedelta(days=1)
    #get rid of available in unavailable
    for availability in availabilities:
        date_cursor = availability.available_from
        while date_cursor <= availability.available_to:
            date_to_sting = date_cursor.strftime('%Y-%m-%d')
            unavailable_dates.discard(date_to_sting)
            date_cursor += timedelta(days=1)

    for booking in confirmed_bookings:
       booking_start_date = booking.booking_start
       booking_end_date = booking.booking_end
       date_cursor = booking_start_date
       while date_cursor < booking_end_date:
           date_to_sting = date_cursor.strftime('%Y-%m-%d')
           unavailable_dates.add(date_to_sting)
           date_cursor += timedelta(days=1)

    unavailable_dates = sorted(unavailable_dates)
    if request.method == 'POST':
        start_booking = request.form.get('booking_start')
        end_booking = request.form.get('booking_end')

        if not start_booking or not end_booking:
            flash('Please select dates')
            return redirect(url_for('renter.book_car', car_id=car_id))
        
        booking_start = datetime.strptime(start_booking, '%Y-%m-%d').date()
        booking_end = datetime.strptime(end_booking, '%Y-%m-%d').date()

        if booking_start >= booking_end:
            flash('Invalid')
            return redirect(url_for('renter.book_car', car_id =car_id))
        
        date_cursor = booking_start
        while date_cursor < booking_end:
            date_to_sting = date_cursor.strftime('%Y-%m-%d')
            if date_to_sting in unavailable_dates:
                flash("selected dates are not available")
                return redirect(url_for('renter.book_car', car_id =car_id))
            date_cursor += timedelta(days=1)

        
        
        rental_days = (booking_end - booking_start).days
        total_price = rental_days * float(car.price_per_day)

        try:
            with db.session.begin_nested():
                #check for concurrent bookings
                concurrency_check = db.session.query(Booking).filter(Booking.car_id == car_id, Booking.status == 'confirmed', or_(
                    and_(Booking.booking_start < booking_end, Booking.booking_end > booking_start)
                )).count()
                if concurrency_check > 0:
                    flash("Someone else booked these dates!")
                    db.session.rollback()
                    return redirect(url_for('renter.book_car', car_id=car_id))
                #create new booking
                new_booking = Booking( car_id =car_id, renter_id = session['user_id'], booking_start = booking_start, booking_end = booking_end, status = 'confirmed', total_price = total_price, booking_created = today)
                db.session.add(new_booking)
                overlapping_availabilities = db.session.query(Availability).filter(Availability.car_id == car_id, Availability.available_from <= booking_end, Availability.available_to >= booking_start).all()
                for availability in overlapping_availabilities:
                    if booking_start <= availability.available_from and booking_end >= availability.available_to:
                        db.session.delete(availability)
                    elif booking_start <= availability.available_from < booking_end < availability.available_to:
                        availability.available_from = booking_end
                    elif availability.available_from < booking_start < availability.available_to <= booking_end:
                        availability.available_to = booking_start
                    elif availability.available_from < booking_start and availability.available_to > booking_end:
                        updates_availability = Availability(car_id=car_id, available_from=booking_end, available_to = availability.available_to)
                        availability.available_to = booking_start
                        db.session.add(updates_availability)
            db.session.commit()
            flash('Booking Confirmed')
            return redirect(url_for('renter_home'))
        except Exception as e:
            db.session.rollback()
            flash("An error occurred while booking.")
            return redirect(url_for("renter.book_car", car_id=car_id))
    
    availability_periods = [(availability.available_from.strftime('%Y-%m-%d'), availability.available_to.strftime('%Y-%m-%d')) for availability in availabilities]
    return render_template('book_car.html', car=car,location= location, unavailable_dates=unavailable_dates, availability_periods=availability_periods)

@renter_blueprint.route('/booking_history')
def booking_history():
    if 'user_id' not in session or session.get('role') != 'renter':
        flash("You need to login")
        return redirect(url_for('login'))
    
    renter_id = session['user_id']
    #when a booking has passed its status is updated
    update_confirmed = text("""UPDATE booking SET status = 'completed' WHERE status = 'confirmed' AND booking_end < DATE('now')""")
    db.session.execute(update_confirmed)
    db.session.commit()
    #get bookigns and statistics
    bookings = db.session.query(Booking, Car).join(Car, Booking.car_id == Car.car_id).filter(Booking.renter_id == renter_id).all()
    avg_price_spent = db.session.query(func.avg(Booking.total_price)).filter(Booking.renter_id == renter_id, Booking.status != "cancelled").scalar()
    avg_booking_length = db.session.query(func.avg(func.julianday(Booking.booking_end)-func.julianday(Booking.booking_start))).filter(Booking.renter_id == renter_id, Booking.status != "cancelled").scalar()
    avg_booking_length = round(avg_booking_length, 2) if avg_booking_length else 0
    most_used_car = db.session.query(Car.make, Car.model, Car.year, func.count(Booking.booking_id).label('cnt')).join(Booking, Booking.car_id == Car.car_id).filter(Booking.renter_id == renter_id, Booking.status != "cancelled").group_by(Car.car_id).order_by(func.count(Booking.booking_id).desc()).first()
    if most_used_car:
        most_used_car = {
            'make': most_used_car.make,
            'model': most_used_car.model,
            'year': most_used_car.year
        }
    else:
        most_used_car = None
    
    current_day = datetime.today().date()
    return render_template('booking_history.html', bookings=bookings, avg_price_spent=avg_price_spent,avg_booking_length = avg_booking_length, most_used_car = most_used_car, current_day = current_day)


@renter_blueprint.route('/cancel_booking/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    if 'user_id' not in session or session.get('role') != 'renter':
        flash("You need to login")
        return redirect(url_for('login'))
    renter_id = session['user_id']
    booking = db.session.query(Booking).filter_by(booking_id=booking_id, renter_id=renter_id).first()
    if not booking:
        flash("Booking not found")
        return redirect(url_for('renter.booking_history'))
    
    if booking.status != "confirmed":
        flash("Booking already happened or was canceled")
        return redirect(url_for('renter.booking_history'))
    
    current_date = datetime.today().date()
    days_before_start = (booking.booking_start - current_date).days
    print(days_before_start)
    #cant cancel bookings within 3 days of the start
    if days_before_start < 3:
        flash("It is too late to cancel! Within 3 days of the start date.")
        return redirect(url_for('renter.booking_history'))
    

    
    try:
        with db.session.begin_nested():
            booking.status = 'cancelled'
            db.session.add(booking)
            new_availability = text("""INSERT INTO availability (car_id, available_from, available_to) VALUES (:car_id, :start, :end)""")
            db.session.execute(new_availability, {"car_id": booking.car_id, "start" : booking.booking_start, "end" : booking.booking_end})

            merged = False
            #once a booking is canceled that time goes back into avaialbility
            while not merged:
                merged = True
                availabilities = db.session.execute(text("""SELECT availability_id, available_from, available_to FROM availability
                                                            WHERE car_id = :car_id ORDER BY available_from"""), {"car_id": booking.car_id}).fetchall()
                list_of_availabilities = [(row.availability_id, row.available_from, row.available_to) for row in availabilities]
                for i in range(len(list_of_availabilities)-1):
                    available_id1, start1, end1 = list_of_availabilities[i]
                    available_id2, start2, end2 = list_of_availabilities[i+1]
                    if end1 >= start2:
                        new_start = min(start1, start2)
                        new_end = max(end1, end2)
                        delete_availability = text("""DELETE FROM availability WHERE availability_id IN (:available_id1, :available_id2)""")
                        db.session.execute(delete_availability, {"available_id1": available_id1, "available_id2": available_id2})
                        new_merge_availability = text("""INSERT INTO availability (car_id, available_from, available_to)
                                                    VALUES(:car_id, :new_start, :new_end)""")
                        db.session.execute(new_merge_availability, {"car_id": booking.car_id, "new_start": new_start, "new_end": new_end})
                        merged = False
                        break

        db.session.commit()
        flash("Booking Canceled")
        return redirect(url_for("renter.booking_history"))
    except Exception as e:
        print("error ?")
        db.session.rollback()
        flash("An error occurred")
        return redirect(url_for("renter.booking_history"))




