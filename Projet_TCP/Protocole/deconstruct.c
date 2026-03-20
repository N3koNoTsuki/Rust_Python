enum { Read_Header, Check_Header, Read_Payload, Check_payload };
== > 1 2 3 4

        void
        Read_Header(void) {
  Lire_socket();
}

void Check_Header() {
  Check_signature(); // On se realigne si decalage
  Calcule_signature();
}

Read_Payload() {
  Lire_socket();
  if socket
    .DN { Check_payload() }
  else {
    Erreur_H()
  }
}

Check_payload() {
  Check_buffer_all_read();
  if ok {
    Set Payload_Ready
  } else {
    Set Read_Payload // On relit le buffer
  }
}

Erreur_H() {}
