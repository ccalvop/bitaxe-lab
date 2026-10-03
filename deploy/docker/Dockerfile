# Bitaxe collector in loop mode: one sample every BITAXE_INTERVAL seconds into /data.
FROM python:3.12-slim

RUN useradd --system --uid 10001 collector \
 && mkdir /data && chown collector /data

COPY collector/bitaxe_collect.py /app/bitaxe_collect.py

ENV BITAXE_CSV=/data/metrics.csv \
    BITAXE_INTERVAL=300 \
    PYTHONUNBUFFERED=1

USER collector
VOLUME /data
ENTRYPOINT ["python", "/app/bitaxe_collect.py"]
