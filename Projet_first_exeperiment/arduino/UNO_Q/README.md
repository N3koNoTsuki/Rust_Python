# 😎 test

### Description test du bridge

## Beug

Pour que le projet marche vous devez editer le code de **zephyrCommon.cpp** sous la board **uno q** folder under **arduino uno q** :

**`$HOME/.arduino15/packages/arduino/hardware/zephyr/0.53.1/cores/arduino/zephyrCommon.cpp`**

**files name** : `zephyrCommon.cpp`

**replace** :
```C
void delayMicroseconds(unsigned int us) {
	k_sleep(K_USEC(us));
}
```

**with:**
```C
// void delayMicroseconds(unsigned int us) {
// 	k_sleep(K_USEC(us));
// }
void delayMicroseconds(unsigned int us) {
	//  ignore small values
	if (us <= 1) return;
	//  optional adjust loop here
	// start the clock
	uint32_t start = micros();
	while (micros() - start < us){
		//  empty loop
	}
	return;
}
```

**Voir** : `https://forum.arduino.cc/t/ds18b20-onewire-not-detected-on-arduino-uno-q-zephyr-timing-gpio-rpc-issue/1422785/96`

**Après modification** : Redémarrer Arduino IDE → Recompiler → Téléverser


