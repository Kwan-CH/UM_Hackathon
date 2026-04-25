from datetime import datetime
# timestamp
def get_timestamp():
    time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return str(time)