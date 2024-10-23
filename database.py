import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import mysql.connector
import threading
import time

# Machine configurations
machines = {
    "fanuc": {"cycle_time": 2.32, "topics": ["R01/ON", "R02/ON", "R12/OFF"]}
}

mqttServer = "127.0.0.1"

db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "machine"
}

connection = mysql.connector.connect(**db_config)
cursor = connection.cursor()

def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    for machine, config in machines.items():
        for topic in config["topics"]:
            client.subscribe(f"{machine}/{topic}")

def on_message(client, userdata, msg):
    print(f"{msg.topic}: {msg.payload.decode()}")
    process_message(msg)

def reconnect_db():
    global connection, cursor
    try:
        connection.ping(reconnect=True, attempts=3, delay=5)
    except mysql.connector.Error as err:
        print(f"Error reconnecting to database: {err}")
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

def process_message(msg):
    reconnect_db()
    machine, topic = msg.topic.split("/", 1)
    c = msg.payload.decode()
    if topic == "R01/ON":
        if c == "true":
            qry = "INSERT INTO fanuc (date, start_time, status) VALUES (CURDATE(), CURTIME(), 'RUNNING')"
        else:
            qry = "UPDATE fanuc SET end_time = CURTIME(), duration = TIMEDIFF(CURTIME(), start_time) WHERE duration IS NULL AND status = 'RUNNING'"
    elif topic == "R02/ON":
        if c == "true":
            qry = "INSERT INTO fanuc (date, start_time, status) VALUES (CURDATE(), CURTIME(), 'DOWN')"
        else:
            qry = "UPDATE fanuc SET end_time = CURTIME(), duration = TIMEDIFF(CURTIME(), start_time) WHERE duration IS NULL AND status = 'DOWN'"
    elif topic == "R12/OFF":
        if c == "true":
            qry = "INSERT INTO fanuc (date, start_time, status) VALUES (CURDATE(), CURTIME(), 'IDLE')"
        else:
            qry = "UPDATE fanuc SET end_time = CURTIME(), duration = TIMEDIFF(CURTIME(), start_time) WHERE duration IS NULL AND status = 'IDLE'"

    cursor.execute(qry)
    connection.commit()

def mqtt_thread_func():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(mqttServer, 1883, 0)
    client.loop_forever()

mqtt_thread = threading.Thread(target=mqtt_thread_func)
mqtt_thread.start()

seconds = 0

def calculate_oee(machine):
    global seconds
    config = machines[machine]
    plan = 0

    # Get plan from the oee table
    cursor.execute("SELECT plan FROM oee WHERE date = CURDATE() AND id = %s", (machine,))
    result = cursor.fetchone()

    if result and result[0] is not None:
        plan = int(result[0])
    else:
        plan = 0

    if seconds % int(config["cycle_time"] * 60) == 0:
        plan += 1

    # Get actual count from the fanuc table
    cursor.execute("SELECT COUNT(*) FROM fanuc WHERE date = CURDATE() AND status = 'RUNNING' AND duration IS NOT NULL AND duration >= '00:02:00'")
    actual = cursor.fetchone()[0]

    percent = (actual / plan) * 100 if plan > 0 else 0
    percentage = f"{percent:.2f} %"

    cursor.execute(
        "INSERT INTO oee (id, date, plan, actual, percentage) VALUES (%s, CURDATE(), %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE actual = %s, plan = %s, percentage = %s",
        (machine, plan, actual, percentage, actual, plan, percentage)
    )

    connection.commit()

while True:
    for machine in machines.keys():
        calculate_oee(machine)
    
    current_time = int(time.strftime("%H%M"))
    current_day = int(time.strftime("%w"))

    time_periods = [
        (740, 1000),
        (1010, 1145 if current_day == 5 else 1200),
        (1300 if current_day == 5 else 1245, 1415),
        (1425, 1545 if current_day == 5 else 1615),
        (1630 if current_day == 5 else 0, 1645 if current_day == 5 else 0)
    ]

    in_time_period = any(start <= current_time < end for start, end in time_periods)

    if in_time_period:
        time.sleep(1)
        seconds += 1

    if ((current_time == 1615 and current_day != 5) or
        (current_time == 1645 and current_day == 5)):
        for machine, config in machines.items():
            for topic in config["topics"]:
                publish.single(f"{machine}/{topic}", payload="false", hostname=mqttServer)
        time.sleep(60)  # Delay for a minute to avoid publishing multiple times
 