FROM python:3.12-slim
WORKDIR /app
COPY spellcar_server.py .
USER nobody
EXPOSE 8787
CMD ["python", "-u", "spellcar_server.py"]
