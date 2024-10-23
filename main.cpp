#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <PubSubClient.h>

const char* machine = "fanuc";
const int relay1Pin = D0;  // only GPIO 16 (D0) can set to INPUT_PULLDOWN
const int relay2Pin = D8;  // input of D8 always pulled to GND

bool firstState = false;
bool secondState = false;
bool thirdState = false;

const char* ssid ="Yanni kost";
const char* password = "ismail45";
const char* mqttServer = "192.168.1.7";
const int mqttPort = 1883;

WiFiClient espClient;
PubSubClient client(espClient);

void connectWiFi() {
  Serial.print("\nConnecting to WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi");
}

void connectMQTT() {
  Serial.println("Connecting to MQTT...");
  client.setServer(mqttServer, mqttPort);
  while (!client.connected()) {
    if (client.connect("ESP8266Client")) {
      Serial.println("Connected to MQTT");
    } else {
      Serial.print("Failed to connect to MQTT: ");
      Serial.println(client.state());
      delay(5000); // Wait 5 seconds before retrying
    }
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.println("Connecting to MQTT...");
    if (client.connect("ESP8266Client")) {
      Serial.println("Connected to MQTT");
    } else {
      delay(1000);
    }
  }
}

void publishMessage(const char* topic, const char* payload) {
  if (!client.publish(topic, payload)) {
    Serial.println("Failed to publish message");
  }
}

void setup() {
  Serial.begin(9600);
  connectWiFi();
  connectMQTT();
  pinMode(relay1Pin, INPUT_PULLDOWN_16);
  pinMode(relay2Pin, INPUT);
}

void loop() {
  if (digitalRead(relay1Pin) == HIGH && !firstState) {
    if (digitalRead(relay2Pin) == LOW) {
      firstState = true;
      Serial.println("Relay 1 turned ON");
      char runTopic[20];
      snprintf(runTopic, sizeof(runTopic), "%s%s", machine, "/R01/ON");
      publishMessage(runTopic, "true");
    }
  } else if ((digitalRead(relay1Pin) == LOW || digitalRead(relay2Pin) == HIGH) && firstState) {
    firstState = false;
    Serial.println("Relay 1 turned OFF");
    char runTopic[20];
    snprintf(runTopic, sizeof(runTopic), "%s%s", machine, "/R01/ON");
    publishMessage(runTopic, "false");
  }

  if (digitalRead(relay2Pin) == HIGH && !secondState) {
    secondState = true;
    Serial.println("Relay 2 turned ON");
    char downTopic[20];
    snprintf(downTopic, sizeof(downTopic), "%s%s", machine, "/R02/ON");
    publishMessage(downTopic, "true");
  } else if (digitalRead(relay2Pin) == LOW && secondState) {
    secondState = false;
    Serial.println("Relay 2 turned OFF");
    char downTopic[20];
    snprintf(downTopic, sizeof(downTopic), "%s%s", machine, "/R02/ON"); 
    publishMessage(downTopic, "false");
  }

  if (digitalRead(relay1Pin) == LOW && digitalRead(relay2Pin) == LOW) {
    if (!thirdState) {
      thirdState = true;
      Serial.println("Both relays are OFF");
      char idleTopic[20];
      snprintf(idleTopic, sizeof(idleTopic), "%s%s", machine, "/R12/OFF");
      publishMessage(idleTopic, "true");
    }
  } else if (thirdState){
    thirdState = false;
    char idleTopic[20];
    snprintf(idleTopic, sizeof(idleTopic), "%s%s", machine, "/R12/OFF");
    publishMessage(idleTopic, "false");
  }

  if (!client.connected()) {
    reconnect();
  }
  client.loop();
  delay(1000);  
}
