# Database Tools are shipped with the same pinned MongoDB release as the server.
FROM mongo:8.0.32

WORKDIR /backup

COPY backup.sh run-loop.sh restore.sh /backup/
RUN sed -i 's/\r$//' /backup/backup.sh /backup/run-loop.sh /backup/restore.sh \
    && chmod +x /backup/backup.sh /backup/run-loop.sh /backup/restore.sh

# BACKUP_INTERVAL=0 runs one backup and exits.
ENTRYPOINT ["/backup/run-loop.sh"]
