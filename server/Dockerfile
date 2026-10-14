FROM python:3.12-slim
WORKDIR /app
COPY spellcar_server.py .
RUN mkdir -p /data/videos && chown -R nobody /data
ENV VIDEO_DIR=/data/videos
USER nobody
EXPOSE 8787
CMD ["python", "-u", "spellcar_server.py"]
