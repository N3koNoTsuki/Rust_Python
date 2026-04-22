#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include <stdlib.h>

unsigned long time = 0;

Arduino_LED_Matrix matrix;
uint8_t frame[104];

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);

  // Monitor
  time = millis();
  if (!Monitor.begin()) {
    while (true) {
      digitalWrite(LED_BUILTIN, digitalRead(LED_BUILTIN) ? LOW : HIGH);
      delay(200);
    }
  }
  delay(5000);
  Monitor.print(F("Timestamp Monitor Up : "));
  Monitor.println(millis() - time);

  // Matrix
  time = millis();
  if (!matrix.begin()) {
    Monitor.println(F("matrix hardware is not responding!!"));
    while (true) {}
  }
  matrix.setGrayscaleBits(3);
  Monitor.print(F("Timestamp Matrix Up : "));
  Monitor.println(millis() - time);

  // Bridge (Linux side)
  time = millis();
  if (!Bridge.begin()) {
    Monitor.println(F("Bridge hardware is not responding!!"));
    while (true) {}
  }
  delay(2000);
  boolean start = false;
  while (!start) {
    Bridge.call("linux_started").result(start);
  }
  Monitor.print(F("Timestamp linux Up : "));
  Monitor.println(millis() - time);

  // Pins 2-6 en OUTPUT pour la simulation T->O
  for (int i = 2; i <= 6; i++) {
    pinMode(i, OUTPUT);
  }
}

void loop() {
  digitalWrite(LED_BUILTIN, digitalRead(LED_BUILTIN) ? LOW : HIGH);

  // Compteur binaire sur les pins 2-6, incrémente toutes les secondes
  static int ind = 0;
  static unsigned long lastChange = 0;
  if (millis() - lastChange >= 1000) {
    ind = (ind + 1) % 32;
    if(ind >= 32){
      ind = 0;
    }
    lastChange = millis();
  }
  for (int i = 2; i <= 6; i++) {
    digitalWrite(i, (ind >> (i - 2)) & 0x01);
  }

  // Lecture état des pins → T->O vers PLC
  int pinState  = digitalRead(2);
  int pinState2 = digitalRead(3);
  int pinState3 = digitalRead(4);
  int pinState4 = digitalRead(5);
  int pinState5 = digitalRead(6);

  int input = (pinState  << 0) | (pinState2 << 1) | (pinState3 << 2)
            | (pinState4 << 3) | (pinState5 << 4);

  Monitor.print(F("T->O input: 0x"));
  Monitor.println(input, HEX);

  time = millis();
  Bridge.notify("receive_cip_data", input);
  Monitor.print(F("Bridge notify (ms): "));
  Monitor.println(millis() - time);

  // Lecture O->T (données envoyées par le PLC)
  int outputData = 0;
  time = millis();
  Bridge.call("send_cip_data").result(outputData);
  Monitor.print(F("Bridge call (ms): "));
  Monitor.println(millis() - time);
  Monitor.print(F("O->T output: 0x"));
  Monitor.println(outputData, HEX);

  // Affichage sur la matrice LED : 8 bits de outputData = 8 colonnes (stride=13)
  memset(frame, 0, sizeof(frame));
  for (int bit = 0; bit < 8; bit++) {
    uint8_t brightness = ((outputData >> bit) & 0x01) ? 7 : 0;
    for (int row = 0; row < 8; row++) {
      frame[bit + row * 13] = brightness;
    }
  }
  matrix.draw(frame);
}
