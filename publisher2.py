import paho.mqtt.publish as publish
import time
import random

mqttServer = "127.0.0.1"

# Topics yang akan di-publish
topics = [
    "fanuc/R01/ON",
    "fanuc/R02/ON",
    "fanuc/R12/OFF"
]

# Fungsi untuk mengirimkan data ke setiap topic
def publish_dummy_data():
    while True:
        # Mengirim data dummy secara acak
        for topic in topics:
            # Simulasi nilai true/false secara acak
            payload = "true" if random.choice([True, False]) else "false"
            print(f"Publishing to {topic}: {payload}")
            publish.single(topic, payload=payload, hostname=mqttServer)
        
        # Tunggu sebelum publish data berikutnya
        time.sleep(5)

if __name__ == "__main__":
    publish_dummy_data()
