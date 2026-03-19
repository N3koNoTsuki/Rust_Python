// =========================
// FILE: tx_unoq_sender.ino
// =========================
#include <Arduino_RouterBridge.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Arduino_LED_Matrix.h>
#include <SPI.h>
#include <RF24.h>
#include <stdlib.h>
#include <avr/dtostrf.h>

#include "header.h"

#define ONE_WIRE_BUS 10
#define PIN_CE  8
#define PIN_CSN 7

// global for matrix
Arduino_LED_Matrix matrix;
uint8_t array[104];
int ind = 0;

// global for sensor
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);
float c = DEVICE_DISCONNECTED_C;

// global for radio
RF24 radio(PIN_CE, PIN_CSN);
uint8_t address[][6] = { "1Node", "2Node" };
bool radioNumber = 0;

// global for timestamp
unsigned long time = 0;



void setup() {


  // Setting up lifeline
  pinMode(LED_BUILTIN, OUTPUT);

  
  // Monitor
  time = millis();
  if(!Monitor.begin()){
    while(true){
      digitalWrite(LED_BUILTIN, digitalRead(LED_BUILTIN) ? LOW : HIGH); 
      delay(200);
    }
  }
  delay(5000);
  Monitor.print(F("Timestamp Monitor Up : "));
  Monitor.println(millis() - time);

  // Bridge (Linux side)
  time = millis();
  if(!Bridge.begin()) {
    Monitor.println(F("Bridge hardware is not responding!!"));
    while(true) {};
  }
  else {
    Monitor.println(F("Configuration Bridge finaliser"));
  }
  delay(2000);
  boolean start = false;
  while (!start) {
    Bridge.call("linux_started").result(start);
  }
  Monitor.print(F("Timestamp linux Up : "));
  Monitor.println(millis() - time);

  // Matrix
  time = millis();
  if(!matrix.begin()){
    Monitor.println(F("matrix hardware is not responding!!"));
    while(true) {};
  }
  else {
    Monitor.println(F("Configuration matrix finaliser"));
  }
  matrix.setGrayscaleBits(3);
  Monitor.print(F("Timestamp Matrix Up : "));
  Monitor.println(millis() - time);

  // Temp sensor
  time = millis();
  sensors.begin();
  Monitor.print(F("Timestamp Sensor Up : "));
  Monitor.println(millis() - time);

  // Radio
  time = millis();
  if (!radio.begin()) {
    Monitor.println(F("radio hardware is not responding!!"));
    while (1) {}
  } 
  else {
    Monitor.println(F("Configuration radio finaliser"));
  }
  Monitor.print(F("Timestamp radio Up : "));
  Monitor.println(millis() - time);

  // Setting up TX
  time = millis();
  radio.setPALevel(RF24_PA_LOW, 0);
  radio.openWritingPipe(address[radioNumber]);
  radio.stopListening();
  Monitor.println(F("TX READY"));
  Monitor.print(F("Timestamp TX Up : "));
  Monitor.println(millis() - time);
}

void loop() {

  //lifeline 
  digitalWrite(LED_BUILTIN, digitalRead(LED_BUILTIN) ? LOW : HIGH);

  //Acquisition temp from sensor 
  time = millis();
  sensors.requestTemperatures();
  float c = sensors.getTempCByIndex(0);
  Monitor.print(F("Data received from sensors in (ms) : ")); 
  Monitor.println(millis() - time); 
  if (c == DEVICE_DISCONNECTED_C) { 
    Monitor.println(F("TEMP ERR")); 
  } 
  else {
    //Sending Temps from bridge 
    time = millis(); 
    Bridge.notify("python_func", c); 
    Monitor.print(F("temp send : "));
    Monitor.println(c); 
    Monitor.print(F("Data send Bridge in (ms) : "));
    Monitor.println(millis() - time); 
    //Sending Temps from radio 
    time = millis(); 
    char message[32]; 
    dtostrf(c, 4, 2, message);
    Monitor.println(c);
    bool report = radio.write(message, sizeof(message)); 
    Monitor.print(F("Timestamp Data send in (ms) : ")); 
    Monitor.println(millis() - time); 
    if (report) {
      Monitor.print(F("Transmission successful! "));
      Monitor.print(F("Sent: ")); 
      Monitor.println(c); 
    } 
    else {
      Monitor.println(F("Transmission failed or timed out")); 
    } 
  }

  
  // Update matrix animation
  time = millis();
  for (int i = 0; i < 104; i++) {
    array[i] = design[ind][i];
  }
  ind = (ind + 1) % 10;
  matrix.draw(array);
  Monitor.print(F("Timestamp Matrix update in (ms) : "));
  Monitor.println(millis() - time);
}
