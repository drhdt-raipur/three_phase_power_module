// =============================================================
//  3-Channel 20 kHz PWM  —  Arduino UNO R4 WiFi
//  Uses pwm.h (verified working) for signal generation.
//  PWM starts immediately on power-up, no GUI needed.
//  GUI can connect later and change settings live.
//
//  Pins:
//    D3  — Channel A (Phase 0°   fixed)
//    D6  — Channel B (Phase 120° default)
//    D9  — Channel C (Phase 240° default)
//
//  NOTE: pwm.h does not support hardware phase offset.
//  Phase is approximated by delaying channel start in setup().
//  Once running, phase relationships are stable (all timers
//  free-run at the same frequency, tiny startup skew only).
//
//  Serial commands (115200 baud):
//    SET FREQ <hz>        e.g. SET FREQ 20000
//    SET DUTY <percent>   e.g. SET DUTY 50
//    SET PHASE_B <deg>    e.g. SET PHASE_B 120
//    SET PHASE_C <deg>    e.g. SET PHASE_C 240
//    GET STATUS
//    STOP
//    START
// =============================================================

#include "pwm.h"

PwmOut pwmA(D3);
PwmOut pwmB(D6);
PwmOut pwmC(D9);

// ── Default settings (change these to your preferred defaults) 
float g_freq    = 20000.0f;   // Hz
float g_duty    = 50.0f;      // %
float g_phase_b = 120.0f;     // degrees
float g_phase_c = 240.0f;     // degrees
bool  g_running = true;

// ── Helpers ───────────────────────────────────────────────────

// Convert phase degrees to microsecond delay at current frequency
uint32_t phase_to_us(float deg) {
  float period_us = 1000000.0f / g_freq;   // e.g. 50 µs at 20 kHz
  return (uint32_t)(period_us * deg / 360.0f);
}

void start_pwm() {
  // Channel A — always phase 0, start first
  pwmA.begin(g_freq, g_duty);

  // Channel B — delayed by phase_b
  uint32_t delay_b = phase_to_us(g_phase_b);
  if (delay_b > 0) delayMicroseconds(delay_b);
  pwmB.begin(g_freq, g_duty);

  // Channel C — delayed from A by phase_c
  // We already waited delay_b, so wait (phase_c - phase_b) more
  // But clamp: if phase_c delay from A is less than delay_b already
  // elapsed, just start immediately.
  float period_us  = 1000000.0f / g_freq;
  uint32_t delay_c = (uint32_t)(period_us * g_phase_c / 360.0f);
  if (delay_c > delay_b) {
    delayMicroseconds(delay_c - delay_b);
  }
  pwmC.begin(g_freq, g_duty);

  g_running = true;
}

void stop_pwm() {
  pwmA.end();
  pwmB.end();
  pwmC.end();
  g_running = false;
}

void send_status() {
  Serial.print(F("{\"freq\":"));
  Serial.print(g_freq, 1);
  Serial.print(F(",\"duty\":"));
  Serial.print(g_duty, 1);
  Serial.print(F(",\"phase_b\":"));
  Serial.print(g_phase_b, 1);
  Serial.print(F(",\"phase_c\":"));
  Serial.print(g_phase_c, 1);
  Serial.print(F(",\"running\":"));
  Serial.print(g_running ? "true" : "false");
  Serial.println(F("}"));
}

// ── Setup — PWM starts here, Serial is optional ───────────────
void setup() {
  Serial.begin(115200);
  // Do NOT wait for Serial — PWM must work without USB connected
  // Serial.begin is safe to call; it just won't block.

  start_pwm();   // <-- PWM is live from this point

  // Only print if a terminal happens to be connected
  delay(100);
  Serial.println(F("# UNO R4 3-Phase PWM ready"));
  Serial.println(F("# Commands: SET FREQ | SET DUTY | SET PHASE_B | SET PHASE_C | GET STATUS | START | STOP"));
  send_status();
}

// ── Loop — parse serial commands from GUI ─────────────────────
void loop() {
  if (!Serial.available()) return;

  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  cmd.toUpperCase();

  // SET FREQ
  if (cmd.startsWith("SET FREQ ")) {
    float v = cmd.substring(9).toFloat();
    if (v >= 100.0f && v <= 200000.0f) {
      g_freq = v;
      if (g_running) {
        stop_pwm();
        start_pwm();
      }
      Serial.print(F("OK FREQ ")); Serial.println(g_freq, 1);
      send_status();
    } else {
      Serial.println(F("ERR freq 100-200000 Hz"));
    }

  // SET DUTY
  } else if (cmd.startsWith("SET DUTY ")) {
    float v = cmd.substring(9).toFloat();
    if (v >= 0.1f && v <= 99.9f) {
      g_duty = v;
      if (g_running) {
        // Duty can be updated without restarting
        pwmA.pulse_perc(g_duty);
        pwmB.pulse_perc(g_duty);
        pwmC.pulse_perc(g_duty);
      }
      Serial.print(F("OK DUTY ")); Serial.println(g_duty, 1);
      send_status();
    } else {
      Serial.println(F("ERR duty 0.1-99.9"));
    }

  // SET PHASE_B
  } else if (cmd.startsWith("SET PHASE_B ")) {
    float v = cmd.substring(12).toFloat();
    if (v >= 0.0f && v < 360.0f) {
      g_phase_b = v;
      if (g_running) {
        stop_pwm();
        start_pwm();
      }
      Serial.print(F("OK PHASE_B ")); Serial.println(g_phase_b, 1);
      send_status();
    } else {
      Serial.println(F("ERR phase_b 0-359.9"));
    }

  // SET PHASE_C
  } else if (cmd.startsWith("SET PHASE_C ")) {
    float v = cmd.substring(12).toFloat();
    if (v >= 0.0f && v < 360.0f) {
      g_phase_c = v;
      if (g_running) {
        stop_pwm();
        start_pwm();
      }
      Serial.print(F("OK PHASE_C ")); Serial.println(g_phase_c, 1);
      send_status();
    } else {
      Serial.println(F("ERR phase_c 0-359.9"));
    }

  // GET STATUS
  } else if (cmd == "GET STATUS") {
    send_status();

  // START
  } else if (cmd == "START") {
    if (!g_running) {
      start_pwm();
    }
    Serial.println(F("OK STARTED"));
    send_status();

  // STOP
  } else if (cmd == "STOP") {
    stop_pwm();
    Serial.println(F("OK STOPPED"));
    send_status();

  } else {
    Serial.print(F("ERR unknown: "));
    Serial.println(cmd);
  }
}
