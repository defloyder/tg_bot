from models import *

# CREATE - добавить нового пользователя
def create_user(session, nickname):
    new_user = User(nickname=nickname)
    session.add(new_user)
    session.commit()
    return new_user

# READ - получить пользователя по ID
def get_user_by_id(session, user_id):
    return session.query(User).filter(User.id == user_id).first()

# UPDATE - обновить никнейм пользователя по ID
def update_user_nickname(session, user_id, new_nickname):
    user = session.query(User).filter(User.id == user_id).first()
    if user:
        user.nickname = new_nickname
        session.commit()
    return user

# DELETE - удалить пользователя по ID
def delete_user(session, user_id):
    user = session.query(User).filter(User.id == user_id).first()
    if user:
        session.delete(user)
        session.commit()
    return user

# CREATE - добавить нового мастера
def create_master(session, name, description=None, photo=None):
    new_master = Master(name=name, description=description, photo=photo)
    session.add(new_master)
    session.commit()
    return new_master

# READ - получить мастера по ID
def get_master_by_id(session, master_id):
    return session.query(Master).filter(Master.id == master_id).first()

# UPDATE - обновить данные мастера по ID
def update_master(session, master_id, name=None, description=None, photo=None):
    master = session.query(Master).filter(Master.id == master_id).first()
    if master:
        if name:
            master.name = name
        if description:
            master.description = description
        if photo:
            master.photo = photo
        session.commit()
    return master

# DELETE - удалить мастера по ID
def delete_master(session, master_id):
    master = session.query(Master).filter(Master.id == master_id).first()
    if master:
        session.delete(master)
        session.commit()
    return master


from datetime import datetime

# CREATE - добавить новую запись
def create_record(session, datetime_value, user_id, master_id):
    new_record = Record(datetime=datetime_value, user_id=user_id, master_id=master_id)
    session.add(new_record)
    session.commit()
    return new_record

# READ - получить запись по ID
def get_record_by_id(session, record_id):
    return session.query(Record).filter(Record.id == record_id).first()

# READ - получить все записи пользователя
def get_records_by_user_id(session, user_id):
    return session.query(Record).filter(Record.user_id == user_id).all()

# READ - получить все записи мастера
def get_records_by_master_id(session, master_id):
    return session.query(Record).filter(Record.master_id == master_id).all()

# UPDATE - обновить дату и время записи по ID
def update_record_datetime(session, record_id, new_datetime):
    record = session.query(Record).filter(Record.id == record_id).first()
    if record:
        record.datetime = new_datetime
        session.commit()
    return record

# DELETE - удалить запись по ID
def delete_record(session, record_id):
    record = session.query(Record).filter(Record.id == record_id).first()
    if record:
        session.delete(record)
        session.commit()
    return record



