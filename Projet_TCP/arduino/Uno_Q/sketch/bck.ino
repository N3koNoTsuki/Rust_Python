#include "Arduino_RouterBridge.h"
#include "Arduino_LED_Matrix.h"
#include "header.h"

Arduino_LED_Matrix matrix;
int data = 0;
uint8_t array[104];
static int ind = 0;

void setup() {
  Monitor.begin();
  matrix.begin();
  matrix.setGrayscaleBits(3);
  Bridge.begin();
  delay(2000);

  boolean start = false;

  // Wait until the python is started
  while(!start)
  {
    Bridge.call("linux_started").result(start);
  }
}

void loop() {
  data++;
  Bridge.notify("python_func", data);
  Monitor.print("Data send : ");
  Monitor.println(data);
  

  for(int i = 0; i < 104; i++) array[i] = design[ind][i];
  ind = (ind + 1) % 10;

  matrix.draw(array);
  delay(1000);
}
