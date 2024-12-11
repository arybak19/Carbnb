from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import Car, Availability, Booking, User, Location
from extensions import db
from sqlalchemy import update, text
from datetime import datetime, timedelta
import json
# initialize a blueprint
leaser_blueprint = Blueprint('leaser', __name__, url_prefix='/leaser')

@leaser_blueprint.route('/add_car', methods=['GET', 'POST'])
def add_car():
    if request.method == "POST":
        #gets the data that is typed in by the leaser
        #fills car table
        make = request.form.get('make')
        model = request.form.get('model')
        year = request.form.get('year')
        price_per_day = request.form.get('price_per_day')
        owner_id = session.get('user_id')

        #fills location table
        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        zip_code = request.form.get('zip_code')
        country = request.form.get('country')
        
        if not owner_id:
            flash("Error: You must be logged in")
            return redirect(url_for('login'))
        #Checks if that location exists already or not
        location_sql = text("""SELECT location_id FROM location 
                            WHERE address = :address AND city = :city AND state = :state AND zip_code = :zip_code AND country = :country""")
        location_sql_result = db.session.execute(location_sql, {
            "address" : address, "city" : city, "state" : state, "zip_code":zip_code, "country" : country
        }).fetchone()

        if location_sql_result:
            location_id = location_sql_result[0]
        else:
            add_location_query = text("""INSERT INTO location (address, city, state, zip_code, country)
                                      VALUES(:address, :city, :state, :zip_code, :country)""")
            db.session.execute(add_location_query, {
                "address" : address, "city" : city, "state" : state, "zip_code":zip_code, "country" : country
            })
            db.session.commit()
            location_id = db.session.execute(location_sql, {
            "address" : address, "city" : city, "state" : state, "zip_code":zip_code, "country" : country
        }).fetchone()[0]
        #adds car to db
        new_car = Car(owner_id = owner_id,make = make, model = model, year = year, price_per_day = price_per_day, location_id = location_id)
        db.session.add(new_car)
        db.session.commit()

        car_id = new_car.car_id
        #add availability
        availability_ranges = request.form.get('availability_ranges')
        if availability_ranges:
            ranges = json.loads(availability_ranges)
            new_ranges = []
            for period in ranges:
                available_from = datetime.strptime(period['start'], "%Y-%m-%d").date()
                available_to = datetime.strptime(period['end'], "%Y-%m-%d").date()
                new_ranges.append((available_from, available_to))
            sorted_ranges = sorted(new_ranges, key=lambda r:r[0])
            for i in range(1,len(sorted_ranges)):
                prev_start, prev_end = sorted_ranges[i-1]
                curr_start, curr_end = sorted_ranges[i]
                if curr_start <= prev_end:
                    flash("Selected Availability ranges cant overlap")
                    db.session.delete(new_car)
                    db.session.commit()
                    return redirect(url_for("leaser.add_car"))
            for available_from, available_to in new_ranges:
                new_availability = Availability(car_id=car_id, available_from=available_from,available_to=available_to)
                db.session.add(new_availability)
            db.session.commit()


        flash("Car Added!")
        return redirect(url_for("leaser_home"))
    return render_template('add_car.html')

@leaser_blueprint.route('/update_car', methods=['GET', 'POST'])
def update_car():
    owner_id = session.get('user_id')
    if not owner_id:
        flash("Error: You must be logged in")
        return redirect(url_for('login'))
    #get all cars owned by the leaser
    sql_query = text("SELECT * FROM car WHERE owner_id = :owner_id")
    result = db.session.execute(sql_query, {"owner_id": owner_id}).fetchall()
    cars = [dict(row._mapping) for row in result]
    #find attribute they want to change
    car_id = request.args.get('car_id', type = int) or request.form.get('car_id', type = int)
    attribute = request.form.get('attribute')
    availabilities = []
    #get everything for the car they chose
    if car_id:
        availability_sql = text("SELECT * FROM availability WHERE car_id= :car_id")
        availability_sql_result = db.session.execute(availability_sql, {"car_id": car_id}).fetchall()
        availabilities = [dict(row._mapping) for row in availability_sql_result]


    if request.method == "POST":
        new_value = request.form.get('new_value')
        
        try:
            with db.session.begin_nested():
                #update availabilities
                if attribute == "availability":
                    availability_ranges = request.form.get("availability_ranges")
                    if availability_ranges:
                        ranges = json.loads(availability_ranges)

                        for period in ranges:
                            available_from = datetime.strptime(period['start'], "%Y-%m-%d").date()
                            available_to = datetime.strptime(period['end'], "%Y-%m-%d").date()
                            #overlap check
                            overlap_check_query = text("""SELECT COUNT(*) as cnt FROM booking WHERE car_id = :car_id AND status = 'confirmed' AND NOT(booking_end <= :available_from OR booking_start >= :available_to)""")
                            count_of_the_overlap = db.session.execute(overlap_check_query, {"car_id": car_id, "available_from": available_from, "available_to":available_to}).fetchone().cnt
                            #if overlaps then dont do anything
                            if count_of_the_overlap > 0:
                                flash("Cannot add availability, because it overlaps with a current booking")
                                #return redirect(url_for("leaser.update_car", car_id=car_id, attribute='availability'))
                                raise Exception("Availability Overlap")
                            # no over lap go add availability
                        for period in ranges:
                            available_from = datetime.strptime(period['start'], "%Y-%m-%d").date()
                            available_to = datetime.strptime(period['end'], "%Y-%m-%d").date()
                            new_availability = Availability(car_id = car_id, available_from=available_from, available_to=available_to)
                            db.session.add(new_availability)
                        #db.session.commit()
                        flash("Updated")
                    else:
                        flash("No ranges given")
                    return redirect(url_for("leaser.update_car", car_id =car_id, attribute = 'availability'))
                if attribute not in ['make', 'model', 'year', 'price_per_day']:
                    flash("Invalid attribute selected")
                    db.session.rollback()
                    return redirect(url_for("leaser.update_car", car_id=car_id))
                try:
                    #all other attributes
                    if attribute == 'year':
                        new_value = int(new_value)
                    elif attribute == 'price_per_day':
                        new_value = float(new_value)
                    elif attribute in ['make', 'model']:
                        new_value =str(new_value)
                except ValueError:
                    flash("Invalid Value")
                    raise Exception("Invalid Attribute")
                    return redirect(url_for("leaser.update_car", car_id=car_id, attribute = attribute))
                #updates the attribute and the new value
                update_query = text(f"UPDATE car SET {attribute} = :new_value WHERE car_id = :car_id AND owner_id = :owner_id")
                

                db.session.execute(update_query, {"new_value": new_value, "car_id": car_id, "owner_id": owner_id})
                flash(f"Car {attribute} updated successfully")

            db.session.commit()
            return redirect(url_for("leaser.update_car", car_id=car_id))
        except Exception as e:
            db.session.rollback()
            flash(str(e))
            return redirect(url_for("leaser.update_car", car_id=car_id, attribute=attribute))
    return render_template("update_car.html", cars=cars, car_id = car_id, availabilities = availabilities, attribute = attribute)

@leaser_blueprint.route('/delete_availability', methods=['POST'])
def delete_availability():
    owner_id = session.get('user_id')
    if not owner_id:
        flash("Must log in")
        return redirect(url_for('login'))
    availability_id = request.form.get('availability_id')
    car_id = request.form.get('car_id')
    attribute = 'attribute'
    availability_sql = text("""SELECT * FROM availability JOIN car ON availability.car_id = car.car_id
                            WHERE availability.availability_id = :availability_id AND car.owner_id= :owner_id""")
    availability_sql_result = db.session.execute(availability_sql,{"availability_id": availability_id, "owner_id": owner_id}).fetchone()
    if not availability_sql_result:
        return redirect(url_for('leaser.update_car', car_id = car_id, attribute = attribute))
    delete_availability_sql = text("DELETE FROM availability WHERE availability_id = :availability_id")
    try:
        db.session.execute(delete_availability_sql, {"availability_id": availability_id})
        db.session.commit()
    except Exception as e:
        db.session.rollback()
    return redirect(url_for('leaser.update_car', car_id=car_id, attribute = attribute))

@leaser_blueprint.route('/delete_car', methods=['GET', 'POST'])
def delete_car():
    owner_id = session.get('user_id')
    if not owner_id:
        flash("Error: You must be logged in")
        return redirect(url_for('login'))
    #get all cars
    sql_query = text("SELECT * FROM car WHERE owner_id = :owner_id")
    result = db.session.execute(sql_query, {"owner_id": owner_id}).fetchall()
    cars = [dict(row._mapping) for row in result]

    if request.method == "POST":
        car_id = request.form.get('car_id')
    #finds current bookings so they cant be deleted
        current_bookings_query = text("""SELECT COUNT(*) as cnt FROM booking
                                      WHERE car_id = :car_id AND status = 'confirmed' AND booking_end > DATE('now')""")
        current_bookings = db.session.execute(current_bookings_query, {"car_id": car_id}).fetchone().cnt
        if current_bookings > 0:
            flash("Cannot Delete this car as it has a booking ongoing or in the future.")
            return redirect(url_for('leaser.delete_car'))

        verify_owner = text("SELECT * FROM car WHERE car_id = :car_id AND owner_id= :owner_id")
        verify_owner_result = db.session.execute(verify_owner, {"car_id"  :car_id, "owner_id" : owner_id}).fetchone()
        if not verify_owner_result:
            flash("Invalid Car Selected")
            return redirect(url_for('leader.delete_car'))
        #delete car and availability
        delete_car_query = text("DELETE FROM car WHERE car_id= :car_id AND owner_id = :owner_id")
        delete_availability_query = text("DELETE FROM Availability WHERE car_id =:car_id")
        try:
            db.session.execute(delete_availability_query, {"car_id" : car_id})
            delete_result = db.session.execute(delete_car_query, {"car_id"  :car_id, "owner_id" : owner_id})
            
            db.session.commit()
            if delete_result.rowcount == 0:
                flash("Deletion did not work")
            else:
                flash("Car Deleted")
            return redirect(url_for("leaser_home"))
        except Exception as e:
            db.session.rollback()
            flash("Error")
            return redirect(url_for("leaser_home"))
    return render_template("delete_car.html", cars=cars)
@leaser_blueprint.route('/car/<int:car_id>')
def car_details(car_id):
    #gets details for all cars and locations for those cars to be displayed
    car_query = text("SELECT car.car_id AS car_id, car.make AS make, car.model AS model, car.year AS year, car.price_per_day AS price_per_day, location.address AS address, location.city AS city, location.state AS state, location.zip_code AS zip_code, location.country AS country FROM car JOIN location ON car.location_id = location.location_id WHERE car.car_id = :car_id")
    car_query_result = db.session.execute(car_query, {"car_id": car_id}).fetchone()
   #get all availability
    availability_query = text("SELECT * FROM availability WHERE car_id = :car_id")
    availability_query_result = db.session.execute(availability_query, {"car_id" :car_id}).fetchall()
    availability = [dict(row._mapping) for row in availability_query_result]

    if car_query_result:
        car = dict(car_query_result._mapping)
        return render_template('car_details.html', car = car, availability=availability)
    else:
        flash("Error")
        return redirect(url_for("renter_home"))
@leaser_blueprint.route('/leaser_booking_history', methods=['GET'])
def leaser_booking_history():
    if 'user_id' not in session or session.get('role') != 'leaser':
        flash("You need to login")
        return redirect(url_for('login'))
    
    leaser_id = session['user_id']
    #find cars owned by the leaser
    cars_query = text("""SELECT car.car_id, car.make, car.model, car.year, car.price_per_day
                      FROM car
                      WHERE car.owner_id = :leaser_id""")
    cars_result = db.session.execute(cars_query, {"leaser_id": leaser_id}).fetchall()
    cars = [dict(row._mapping) for row in cars_result]
    booking_data = []
    for car in cars:
        #find bookings for each car
        booking_query = text("""SELECT booking.booking_id, booking.booking_start, booking.booking_end, booking.total_price, booking.status, renter.name AS renter_name
                             FROM booking
                             JOIN user AS renter ON booking.renter_id = renter.user_id
                             WHERE booking.car_id = :car_id""")
        booking_results = db.session.execute(booking_query, {"car_id": car['car_id']}).fetchall()
        bookings = [dict(row._mapping) for row in booking_results]

        total_booked = len(bookings)
        #statistics about each car
        avg_length_booking = text("""SELECT AVG(julianday(booking_end)-julianday(booking_start)) as avg_length
                                  FROM booking
                                  WHERE car_id = :car_id AND NOT status = 'cancelled'""")
        
        avg_length_booking_result = db.session.execute(avg_length_booking, {"car_id": car['car_id']}).fetchone()
        avg_length = round(avg_length_booking_result.avg_length, 2) if avg_length_booking_result and avg_length_booking_result.avg_length else 0
        unique_renters_query = text("""SELECT COUNT(DISTINCT renter_id) as unique_renters
                                    FROM booking
                                    WHERE car_id = :car_id AND NOT status = 'cancelled'""")
        unique_renters_result = db.session.execute(unique_renters_query, {"car_id": car['car_id']}).fetchone()
        unique_renters = unique_renters_result.unique_renters if unique_renters_result and unique_renters_result.unique_renters else 0

        total_revenue = sum(booking['total_price'] for booking in bookings if not booking['status'] == 'cancelled')
        #add date for html
        booking_data.append({
            "car":car,
            'bookings': bookings,
            'total_revenue':total_revenue,
            'total_booked': total_booked,
            'avg_length' : avg_length,
            'unique_renters': unique_renters
        })
    
   
    return render_template('leaser_booking_history.html', booking_data=booking_data)


