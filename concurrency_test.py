import threading
import requests
import time

# Adjust these values as needed
BASE_URL = "http://127.0.0.1:5000"
CAR_ID = 16
BOOKING_START = "2025-01-10"
BOOKING_END = "2025-01-12"

# Two renter accounts (must be pre-created)
USER_A = {"email": "mrybak@gmail.com", "password": "1234", "role": "renter"}
USER_B = {"email": "yrybak@charter.net", "password": "@Marley01", "role": "renter"}

def login_user(user_credentials):
    login_url = f"{BASE_URL}/login"
    session = requests.Session()
    response = session.post(login_url, data=user_credentials, allow_redirects=True)
    
    # Check if redirected to renter_home or leaser_home
    if response.url.endswith('/renter_home') or response.url.endswith('/leaser_home'):
        print(f"Logged in as {user_credentials['email']}")
        return session
    else:
        print(f"Failed to log in as {user_credentials['email']}: {response.text[:100]}...")
        return None


def book_car(session, car_id):
    book_url = f"{BASE_URL}/renter/book_car/{car_id}"
    data = {
        "booking_start": BOOKING_START,
        "booking_end": BOOKING_END
    }
    response = session.post(book_url, data=data)
    print(f"User {session.cookies.get_dict()} - Status: {response.status_code}, Response: {response.text}")

def simulate_user(session, delay=0):
    # Delay to simulate one user clicking slightly later
    time.sleep(delay)
    book_car(session, CAR_ID)

if __name__ == "__main__":
    # Log in both users
    session_a = login_user(USER_A)
    session_b = login_user(USER_B)

    if not session_a or not session_b:
        print("One or both users could not log in, aborting test.")
        exit(1)

    # Create two threads: user A tries to book immediately, user B tries 1 second later
    thread_a = threading.Thread(target=simulate_user, args=(session_a, 0))
    thread_b = threading.Thread(target=simulate_user, args=(session_b, 1))

    start_time = time.time()

    # Start both threads
    thread_a.start()
    thread_b.start()

    # Wait for both to finish
    thread_a.join()
    thread_b.join()

    end_time = time.time()
    print(f"Test completed in {end_time - start_time:.2f} seconds.")
