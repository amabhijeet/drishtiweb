"""MySQL schema for the staff review and video-editing workspace.

Core processing tables are initialized by the Drishti FastAPI service first.
"""
def initialize_schema(conn):
    statements = [
        """CREATE TABLE IF NOT EXISTS web_reports (
            id VARCHAR(128) PRIMARY KEY, source VARCHAR(32), source_id VARCHAR(128),
            original_lat DOUBLE, original_lon DOUBLE, lat DOUBLE, lon DOUBLE,
            confidence DOUBLE, evidence TEXT, captured VARCHAR(64),
            title VARCHAR(255) DEFAULT 'Pothole', description TEXT,
            place VARCHAR(255) DEFAULT '', severity VARCHAR(64) DEFAULT 'Unassessed',
            status VARCHAR(32) DEFAULT 'Draft', gps VARCHAR(255) DEFAULT 'Valid coordinate format',
            discrepancy DOUBLE, INDEX web_reports_status (status)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS web_media (
            id VARCHAR(128) PRIMARY KEY, report VARCHAR(128), kind VARCHAR(32),
            name VARCHAR(255), data LONGBLOB,
            INDEX web_media_report (report)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS web_video_clips (
            id VARCHAR(128) PRIMARY KEY, segment_id VARCHAR(128) NOT NULL,
            title VARCHAR(100) NOT NULL,
            `start` DOUBLE NOT NULL, `end` DOUBLE NOT NULL,
            author VARCHAR(128) NOT NULL,
            created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX web_video_clips_segment (segment_id, created),
            CONSTRAINT fk_clip_segment FOREIGN KEY (segment_id) REFERENCES segments(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS web_audit (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actor VARCHAR(128), report VARCHAR(128), action LONGTEXT,
            INDEX web_audit_report (report)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    ]
    for statement in statements:
        conn.execute(statement)
