#include <SPI.h>
#include "RF24.h"

#define CE_PIN 8
#define CSN_PIN 7
RF24 radio(CE_PIN, CSN_PIN);
int cycle = 0;
uint8_t address[][6] = { "1Node", "2Node" };
bool radioNumber = 1; 
char message[30] = {0};
void setup() {

  Serial.begin(9600);
  delay(1000);

  
  if (!radio.begin()) {
    Serial.println(F("radio hardware is not responding!!"));
    while (1) {}  
  }
  else
  {
    Serial.println(F("Radio Up"));
  }
  radio.setPALevel(RF24_PA_LOW,0); 
  radio.openReadingPipe(1, address[!radioNumber]); 
  radio.startListening();  
} 

void loop() {


  uint8_t pipe;
  if (radio.available(&pipe)) {              // is there a payload? get the pipe number that received it
    uint8_t bytes = radio.getPayloadSize();  // get the size of the payload
    radio.read(&message, bytes);             // fetch payload from FIFO
    Serial.print(cycle);
    Serial.print(F(" Received "));
    Serial.print(bytes);  // print the size of the payload
    Serial.print(F(" bytes on pipe "));
    Serial.print(pipe);  // print the pipe number
    Serial.print(F(": "));
    Serial.println(message);  // print the payload's value
    cycle++;
  }
  
}  
