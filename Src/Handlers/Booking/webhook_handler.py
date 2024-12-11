from flask import Flask, request
from sqlalchemy.exc import SQLAlchemyError
from database.database import SessionFactory
from database.models import Booking

app = Flask(__name__)

@app.route('/yookassa_webhook', methods=['POST'])
def yookassa_webhook():
    data = request.json
    if data['event'] == 'payment.succeeded':
        payment_id = data['object']['id']
        try:
            with SessionFactory() as session:
                booking = session.query(Booking).filter_by(payment_id=payment_id).first()
                if booking and booking.status == "pending_payment":
                    booking.status = "confirmed"
                    session.commit()
                    print(f"Запись {booking.booking_id} подтверждена после успешной оплаты.")
        except SQLAlchemyError as e:
            print(f"Ошибка базы данных при обработке вебхука: {e}")
            return "Error", 500
        return "OK", 200
    return "Unhandled event", 400
