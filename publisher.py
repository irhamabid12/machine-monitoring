import random
import time
import paho.mqtt.client as mqtt

# Fungsi ini untuk mem-publish data dummy ke topik MQTT
def publish_data():
    client = mqtt.Client()
    client.connect("127.0.0.1", 1883, 60)

    while True:
        # Dummy data
        run_data = random.choice([True, False])
        idle_data = random.choice([True, False])
        down_data = random.choice([True, False])

        # Publish data dummy ke topik yang sesuai
        client.publish("fanuc/status", str(run_data).lower())
        client.publish("fanuc/metrics", str(int(idle_data)))
        client.publish("fanuc/down", str(down_data).lower())

        print(f"Published data - run: {run_data}, idle: {idle_data}, down: {down_data}")

        time.sleep(2)  # Interval waktu publish
if __name__ == "__main__":
    publish_data()