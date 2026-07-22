# Atmos — Remaining Hardware To Buy (system bring-up)

Cross-referenced against parts already owned (ESP32-S3 devkit, DS3231
modules, BME280 module, microSD readers, breadboards — July 2026 orders).
Board-level chips/passives are NOT here; they come with the PCB fab BOM.

| # | What it is (plain English) | Exact part |
|---|---|---|
| 1 | The long-range radio that sends data home | HopeRF **RFM95W-915S2** (breadboard-friendly option: Adafruit #3072 breakout) |
| 2 | Antenna for that radio | 915 MHz whip with **SMA male** plug (e.g. Linx ANT-916-CW-HWR-SMA) |
| 3 | Antenna jack on the board | **Amphenol 132134** SMA jack, vertical through-hole (now on the schematic BOM as J6) |
| 4 | Air-quality dust sensor | Plantower **PMS5003** (ships with its 1.25 mm 8-pin cable) |
| 5 | Lightning detector board | **Playing With Fusion SEN-39003** (AS3935, factory-calibrated) — plugs into header J1 via 0.1″ header or Qwiic→SDA/SCL. **Do not buy Amazon CJMCU clones** (common dead-antenna units). SparkFun SEN-15441 is a SPI-first fallback if PWF is out of stock. Source: https://www.playingwithfusion.com/productview.php?pdid=135 |
| 6 | Gas/odor (VOC) sensor for prototyping | Adafruit **SGP40** breakout #4829 (the bare SGP40-D-R4 chip is on the fab BOM) |
| 7 | Watch battery that keeps the clock alive | **CR2032** coin cell (its board holder, Keystone 3034, is on the fab BOM) |
| 8 | Main rechargeable battery | 1-cell LiPo ~2500 mAh with **JST-PH** plug (e.g. Adafruit #328/#2011 class) |
| 9 | Solar panel to charge it | **6 V, 2–3 W** panel (matches the CN3791 MPPT setup; e.g. Voltaic P126) |
| 10 | Plug pigtails for battery & solar | **JST-PH 2-pin** pigtail (battery) + **JST-XH 2-pin** pigtail (solar — different family on purpose) |
| 11 | Storage card for data logging | Any 8–32 GB **microSD** (skip if you have a spare) |
