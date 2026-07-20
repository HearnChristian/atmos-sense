#!/usr/bin/env bash
# Kill-safe Freerouting runner for Atmos. Its own cmdline is this script path,
# so `pkill -f run_fr.sh` never matches the jar name.
set -u
JAVA=/home/christian-thomas-hearn/opt/atmos-route/jdk-25.0.3+9-jre/bin/java
JAR=/home/christian-thomas-hearn/opt/atmos-route/freerouting-2.2.4.jar
DSN=/home/christian-thomas-hearn/Desktop/Atmos/Atmos.dsn
SES=/home/christian-thomas-hearn/Desktop/Atmos/Atmos.ses
LOG=/home/christian-thomas-hearn/opt/atmos-route/fr_run.log
export FREEROUTING__GUI__ENABLED=false
rm -f "$SES" "$LOG"
# 15 min hard ceiling; big stack for geometry recursion; few optimizer passes.
timeout 900 "$JAVA" -Xss128m -Djava.awt.headless=true -jar "$JAR" \
    -de "$DSN" -do "$SES" -mp 15 > "$LOG" 2>&1
code=$?
echo "freerouting exit=$code" >> "$LOG"
[ -f "$SES" ] && echo "SES bytes=$(stat -c%s "$SES")" >> "$LOG" || echo "NO SES" >> "$LOG"
